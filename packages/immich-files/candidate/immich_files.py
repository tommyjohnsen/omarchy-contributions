#!/usr/bin/env python3
"""Account-scoped, read-only, lazy Immich file access. No server listener."""
import argparse
import subprocess
from dataclasses import dataclass, field
import errno
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time
import threading
from urllib.parse import urlsplit
import uuid

import pyfuse3
import trio
import bounded_curl

# Codex: reserved placeholders prevent accidentally publishing a personal endpoint.
# Release gate: replace these constants with explicit validated account configuration.
SERVER = 'https://immich.example.invalid'
ACCOUNT = 'example-account'
CAP = 2 * 1024**3
RESERVE = 10 * 1024**3
PAGE = 250
CHUNK = 256 * 1024
MAX_JSON = 8 * 1024**2
MAX_NODES = 50000
DIRECTORY_TIMEOUT = 25
CACHE_NAME = re.compile(r'^[0-9a-f-]{36}-[0-9a-f]{16}-[0-9a-f]{16}\.bin$')
PART_NAME = re.compile(r'^[0-9a-f-]{36}-[0-9a-f]{16}-[0-9a-f]{16}\.bin\.[0-9a-f]{12}\.part$')


# Do not widen this based on unversioned API recollection; see pinned excerpt.
def server_origin(value):
    if not isinstance(value,str) or any(ord(ch)<0x21 or ch.isspace() or ch in '\\"' for ch in value):
        raise ValueError('Invalid Immich HTTPS origin')
    parsed=urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Configure an HTTPS origin without credentials or path')
    if parsed.port is not None and parsed.port<1:
        raise ValueError('Invalid Immich HTTPS port')
    return 'https://'+parsed.netloc


# v3.3.5 OpenAPI explicitly requires UUIDv4 for assets and albums.
def asset_id(value):
    parsed = uuid.UUID(str(value))
    if parsed.version != 4:
        raise ValueError('Invalid asset identifier')
    return str(parsed)


def safe_name(value):
    text = re.sub(r'[\x00-\x1f\x7f/\\]', '_', str(value)).strip(' .')
    text = text.encode('utf-8')[:150].decode('utf-8', 'ignore')
    return text or 'Untitled'


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


class API:
    def __init__(self, key, runner=None):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_./+=-]{8,512}', key):
            raise ValueError('Invalid credential')
        self.key = key
        self.invalid_rows = 0
        self.runner = runner

    def request(self, method, path, body=None, byte_range=None, deadline=None):
        allowed = (method == 'GET' and path == '/albums') or (
            method == 'POST' and path == '/search/metadata') or (
            method in ('GET', 'HEAD') and re.fullmatch(r'/assets/[0-9a-f-]{36}/original', path))
        if not allowed:
            raise PermissionError('Unsupported API operation')
        duration = min(20, max(0.1, deadline - time.monotonic())) if deadline else 20
        if deadline and time.monotonic() >= deadline:
            raise OSError(errno.ETIMEDOUT, 'Request deadline reached')
        # curl enforces a whole-transfer deadline, including slow-drip headers.
        # Configuration goes through stdin: the credential is absent from argv,
        # environment, logs and persistent files. No redirects/proxies/curlrc.
        config = [f'url = "{server_origin(SERVER)}/api{path}"', f'request = "{method}"',
                  f'header = "x-api-key: {self.key}"', 'header = "Accept: application/json"',
                  'header = "Accept-Encoding: identity"']
        limit = MAX_JSON
        if byte_range:
            start, end = byte_range
            if method != 'GET' or start < 0 or end < start or end-start+1 > CHUNK:
                raise ValueError('Invalid byte range')
            config.append(f'header = "Range: bytes={start}-{end}"')
            limit = end-start+1
        if body is not None:
            config.extend(['header = "Content-Type: application/json"',
                           'data = ' + json.dumps(json.dumps(body, separators=(',', ':')))])
        args = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--http1.1',
                '--noproxy', '*', '--connect-timeout', '5', '--max-time', str(duration),
                '--include', '--config', '-']
        if method == 'HEAD': args.append('--head')
        else: args.extend(['--max-filesize', str(limit)])
        env = {k:v for k,v in os.environ.items() if not k.lower().endswith('_proxy')}
        try:
            payload=('\n'.join(config)+'\n').encode()
            if self.runner is None:
                cap=128*1024 if method=='HEAD' else limit+128*1024
                result=bounded_curl.run(args,input=payload,timeout=duration+2,env=env,output_limit=cap)
            else:
                result = self.runner(args, input=payload,capture_output=True, timeout=duration+2, env=env)
        except subprocess.TimeoutExpired:
            raise OSError(errno.ETIMEDOUT, 'Immich transfer deadline reached')
        if result.returncode:
            raise OSError(errno.ETIMEDOUT if result.returncode==28 else errno.EIO,
                          'Immich transfer failed')
        raw = result.stdout
        if len(raw) > limit + 128*1024:
            raise OSError(errno.EOVERFLOW, 'Response exceeds limit')
        while True:
            header, separator, raw = raw.partition(b'\r\n\r\n')
            if not separator or len(header) > 128*1024:
                raise OSError(errno.EIO, 'Malformed response headers')
            lines = header.decode('iso-8859-1').split('\r\n')
            status = int(lines[0].split()[1])
            if not 100 <= status < 200: break
        headers = {}
        for line in lines[1:]:
            name, separator, value = line.partition(':')
            if separator: headers[name.lower()] = value.strip()
        if byte_range and headers.get('content-encoding', 'identity').lower() != 'identity':
            raise OSError(errno.EIO, 'Encoded original ranges are not supported')
        expected_status = (200,206) if byte_range else (200,)
        if status not in expected_status:
            raise OSError(errno.EACCES if status in (401,403) else errno.ENOENT if status==404 else errno.EIO,
                          'Immich request failed')
        if len(raw) > limit:
            raise OSError(errno.EOVERFLOW, 'Response exceeds limit')
        return Response(status, headers, raw)

    def data(self, method, path, body=None, deadline=None):
        return json.loads(self.request(method, path, body,deadline=deadline).body)

    def albums(self,deadline=None):
        rows = self.data('GET', '/albums',deadline=deadline)
        if not isinstance(rows, list):
            raise OSError(errno.EIO, 'Malformed album response')
        if len(rows)>5000:
            raise OSError(errno.EOVERFLOW, 'Album response exceeds limit')
        valid=[]
        for row in rows:
            try:
                if not isinstance(row,dict) or not isinstance(row.get('albumName'),str):
                    raise ValueError('Malformed album')
                valid.append((asset_id(row['id']),safe_name(row['albumName'])))
            except (KeyError,ValueError,TypeError,AttributeError):
                self.invalid_rows += 1
        return valid

    def search(self, filters, cursor=None, deadline=None):
        body = {'size':PAGE, 'withExif':True, 'filter':filters,
                'orderBy':{'field':'fileCreatedAt','direction':'desc'}}
        if cursor:
            if not isinstance(cursor,str) or not cursor.isascii() or len(cursor)>4096:
                raise ValueError('Invalid cursor')
            body['cursor']=cursor
        response=self.data('POST','/search/metadata',body,deadline=deadline)
        result=response.get('assets') if isinstance(response,dict) else None
        if not isinstance(result,dict) or not isinstance(result.get('items'),list):
            raise OSError(errno.EIO,'Malformed page response')
        rows=result['items']
        if len(rows)>PAGE:
            raise OSError(errno.EOVERFLOW,'Page response exceeds limit')
        valid=[]
        for row in rows:
            try:
                if not isinstance(row,dict):raise ValueError('Malformed asset')
                aid=asset_id(row['id'])
                if row.get('isTrashed') or row.get('isOffline'): continue
                row=dict(row);row.pop('_size',None);row['id']=aid;valid.append(row)
            except (KeyError,ValueError,TypeError,AttributeError):
                self.invalid_rows += 1
        cursor=result.get('nextCursor')
        if cursor is not None and (not isinstance(cursor,str) or not cursor.isascii() or len(cursor)>4096):
            raise OSError(errno.EOVERFLOW,'Invalid next-page cursor')
        return valid,cursor

    def size(self,row,deadline=None):
        cached=row.get('_size')
        if isinstance(cached,int) and not isinstance(cached,bool) and 0<=cached<2**63:return cached
        value=(row.get('exifInfo') or {}).get('fileSizeInByte')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or value<0:
            value=self.request('HEAD','/assets/'+asset_id(row['id'])+'/original',deadline=deadline).headers.get('content-length','')
            if not isinstance(value,str) or not value.isdecimal():raise OSError(errno.EIO,'Original size unavailable')
        size=int(value)
        if not 0<=size<2**63:raise OSError(errno.EIO,'Invalid original size')
        row['_size']=size
        return size

    def download(self,row,start,end,deadline):
        return self.request('GET','/assets/'+asset_id(row['id'])+'/original',
                            byte_range=(start,end),deadline=deadline)


class Cache:
    def __init__(self,directory,api,cap=CAP,reserve=RESERVE):
        self.path=Path(directory)
        self.path.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise OSError(errno.ELOOP,'Cache must not be a symlink')
        st=self.path.stat()
        if st.st_uid!=os.getuid() or not stat.S_ISDIR(st.st_mode):raise PermissionError('Cache ownership mismatch')
        self.path.chmod(0o700)
        self.dirfd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.lockfd=os.open('.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=self.dirfd)
        fcntl.flock(self.lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.api,self.cap,self.reserve=api,cap,reserve
        self.lock=threading.RLock()
        for name in os.listdir(self.dirfd):
            if PART_NAME.fullmatch(name):
                try:asset_id(name[:36])
                except ValueError:continue
                st=os.stat(name,dir_fd=self.dirfd,follow_symlinks=False)
                if stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and st.st_nlink==1:
                    os.unlink(name,dir_fd=self.dirfd)
        # Claude Code review: low free space must block new content reads, not
        # read-only metadata browsing. Eviction still runs; never relax read caps.
        try:
            self.make_room(0)
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise

    def key(self,row,offset):
        fingerprint=hashlib.sha256((str(row.get('checksum',''))+'|'+str(row.get('fileModifiedAt',''))).encode()).hexdigest()[:16]
        return asset_id(row['id'])+'-'+fingerprint+f'-{offset:016x}.bin'

    def owned(self):
        result=[]
        for name in os.listdir(self.dirfd):
            if not CACHE_NAME.fullmatch(name):continue
            try:asset_id(name[:36])
            except ValueError:continue
            st=os.stat(name,dir_fd=self.dirfd,follow_symlinks=False)
            if stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and st.st_nlink==1:result.append((name,st))
        return result

    def usage(self):
        return sum(os.stat(name,dir_fd=self.dirfd,follow_symlinks=False).st_size
                   for name in os.listdir(self.dirfd) if name!='.lock')

    def free(self):
        st=os.fstatvfs(self.dirfd)
        return st.f_bavail*st.f_frsize

    def make_room(self,needed):
        total=self.usage()
        for name,st in sorted(self.owned(),key=lambda pair:pair[1].st_atime_ns):
            if total+needed<=self.cap and self.free()-needed>=self.reserve:break
            os.unlink(name,dir_fd=self.dirfd);total-=st.st_size
        if total+needed>self.cap or self.free()-needed<self.reserve:
            raise OSError(errno.ENOSPC,'Private cache limit or free-space reserve reached')

    def chunk(self,row,offset,size,deadline):
        name=self.key(row,offset);needed=min(CHUNK,size-offset)
        try:
            st=os.stat(name,dir_fd=self.dirfd,follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_nlink!=1:
                raise PermissionError('Unsafe cache entry')
            valid=st.st_size==needed
            if not valid:os.unlink(name,dir_fd=self.dirfd)
        except FileNotFoundError:valid=False
        if not valid:
            self.make_room(needed)
            result=self.api.download(row,offset,offset+needed-1,deadline)
            # Ignored Range must never turn a sniff/read into a full video download.
            if result.status==206:
                expected=f'bytes {offset}-{offset+needed-1}/{size}'
                if result.headers.get('content-range')!=expected:
                    raise OSError(errno.EIO,'Original byte range mismatch')
            elif not (result.status==200 and offset==0 and needed==size and size<=CHUNK):
                raise OSError(errno.EIO,'Server did not honor byte ranges')
            if len(result.body)!=needed:raise OSError(errno.EIO,'Original range length mismatch')
            if self.free()-needed<self.reserve:raise OSError(errno.ENOSPC,'Free-space reserve reached')
            temp=name+'.'+secrets.token_hex(6)+'.part'
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.dirfd)
            try:
                view=memoryview(result.body)
                while view:
                    if time.monotonic()>deadline:raise OSError(errno.ETIMEDOUT,'Read deadline reached')
                    if self.free()-len(view)<self.reserve:raise OSError(errno.ENOSPC,'Free-space reserve reached')
                    view=view[os.write(fd,view):]
                os.fsync(fd);os.close(fd);fd=-1
                os.replace(temp,name,src_dir_fd=self.dirfd,dst_dir_fd=self.dirfd)
            finally:
                if fd>=0:os.close(fd)
                try:os.unlink(temp,dir_fd=self.dirfd)
                except FileNotFoundError:pass
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.dirfd)
        try:
            os.utime(name,None,dir_fd=self.dirfd,follow_symlinks=False)
            return os.read(fd,needed)
        finally:os.close(fd)

    def read(self,row,offset,length,deadline=None):
        deadline=deadline if deadline is not None else time.monotonic()+24
        if not self.lock.acquire(timeout=max(0, deadline-time.monotonic())):
            raise OSError(errno.ETIMEDOUT,'Read queue deadline reached')
        try:
            if time.monotonic()>=deadline:raise OSError(errno.ETIMEDOUT,'Read deadline reached')
            size=self.api.size(row,deadline=deadline)
            if offset>=size or length==0:return b''
            end=min(size,offset+length);result=bytearray()
            while offset<end:
                if time.monotonic()>deadline:raise OSError(errno.ETIMEDOUT,'Read deadline reached')
                start=(offset//CHUNK)*CHUNK
                data=self.chunk(row,start,size,deadline)
                count=min(end-offset,len(data)-(offset-start))
                if count<=0:raise OSError(errno.EIO,'Incomplete range')
                result.extend(data[offset-start:offset-start+count]);offset+=count
            return bytes(result)
        finally:self.lock.release()

@dataclass
class Node:
    kind: str
    filters: dict = field(default_factory=dict)
    cursor: str | None = None
    row: dict | None = None
    children: list | None = None
    loaded: float = 0


class Filesystem(pyfuse3.Operations):
    def __init__(self, api, cache):
        super().__init__()
        self.api, self.cache = api, cache
        self.nodes = {1: Node('root'), 2: Node('search', {'visibility': {'eq': 'timeline'}}),
                      3: Node('search', {'isFavorite': {'eq': True}, 'visibility': {'eq': 'timeline'}}), 4: Node('albums')}
        self.identities = {}
        self.counter = 5
        self.lock = threading.RLock()
        self.handles = {}
        self.next_handle = 1
        self.limiter = trio.CapacityLimiter(2)
        self.read_limiter = trio.CapacityLimiter(1)
        self.directory_handles = {}
        self.next_directory_handle = 1

    def node(self, key, value):
        if key not in self.identities:
            if self.counter >= MAX_NODES:
                raise OSError(errno.ENOMEM, 'Metadata browsing limit reached; restart the service to start fresh')
            self.identities[key] = self.counter
            self.nodes[self.counter] = value
            self.counter += 1
        return self.identities[key]

    def listing(self, inode):
        with self.lock:
            node = self.nodes[inode]
            if node.kind == 'file':
                raise OSError(errno.ENOTDIR, 'Not a folder')
            if node.children is not None and time.monotonic() - node.loaded < 60:
                return node.children
            kind,filters,cursor=node.kind,dict(node.filters),node.cursor
        albums = self.api.albums() if kind == 'albums' else None
        result = self.api.search(filters,cursor) if kind not in ('root','albums') else None
        with self.lock:
            if kind == 'root':
                children = [('Recent', 2), ('Favorites', 3), ('Albums', 4)]
            elif kind == 'albums':
                children = []
                for aid, name in albums:
                    ino = self.node(('album', aid), Node('search', {'albumIds': {'any': [aid]}}))
                    children.append((name + ' [' + aid + ']', ino))
            else:
                rows, cursor = result
                children = []
                for row in rows:
                    ino = self.node(('file',row['id'],str(row.get('checksum','')),str(row.get('fileModifiedAt',''))), Node('file', row=row))
                    previous = self.nodes[ino].row
                    row = dict(row)
                    if previous and previous.get('checksum') and previous.get('checksum') == row.get('checksum') and previous.get('fileModifiedAt') == row.get('fileModifiedAt'):
                        known = previous.get('_size')
                        if isinstance(known,int) and not isinstance(known,bool) and 0<=known<2**63:
                            row['_size'] = known
                    self.nodes[ino].row = row
                    original = safe_name(row.get('originalFileName', 'Photo'))
                    stem, extension = os.path.splitext(original)
                    extension = extension[:24]
                    children.append((stem + ' [' + row['id'] + ']' + extension, ino))
                if cursor:
                    ino = self.node(('cursor', json.dumps(node.filters, sort_keys=True), cursor), Node('search', node.filters, cursor))
                    children.append(('Next page', ino))
            children.sort(key=lambda item: item[0].casefold())
            node.children, node.loaded = children, time.monotonic()
            return children

    def attributes(self, inode):
        node = self.nodes[inode]
        attr = pyfuse3.EntryAttributes()
        attr.st_ino, attr.st_uid, attr.st_gid = inode, os.getuid(), os.getgid()
        attr.st_mode = (stat.S_IFREG | 0o400) if node.kind == 'file' else (stat.S_IFDIR | 0o500)
        attr.st_nlink = 1 if node.kind == 'file' else 2
        attr.st_size = self.api.size(node.row) if node.kind == 'file' else 0
        stamp = 0
        if node.kind == 'file':
            try:
                stamp = int(datetime.datetime.fromisoformat(node.row.get('fileCreatedAt', '').replace('Z', '+00:00')).timestamp() * 1_000_000_000)
            except (ValueError, TypeError): pass
        attr.st_atime_ns = attr.st_mtime_ns = attr.st_ctime_ns = stamp
        attr.st_blksize = 4096
        attr.st_blocks = (attr.st_size + 511) // 512
        attr.entry_timeout = attr.attr_timeout = 5
        return attr

    async def worker(self, function, *args, limiter=None):
        try:
            with trio.fail_after(25):
                return await trio.to_thread.run_sync(lambda: function(*args), abandon_on_cancel=True, limiter=limiter or self.limiter)
        except trio.TooSlowError:
            raise pyfuse3.FUSEError(errno.ETIMEDOUT)
        except KeyError:
            raise pyfuse3.FUSEError(errno.ENOENT)
        except OSError as error:
            raise pyfuse3.FUSEError(error.errno or errno.EIO)
        except Exception:
            raise pyfuse3.FUSEError(errno.EIO)

    async def getattr(self, inode, ctx=None):
        return await self.worker(self.attributes, inode)

    async def lookup(self, parent_inode, name, ctx=None):
        rows = await self.worker(self.listing, parent_inode)
        for label, inode in rows:
            if label.encode() == name:
                return await self.getattr(inode)
        raise pyfuse3.FUSEError(errno.ENOENT)

    async def opendir(self, inode, ctx=None):
        rows = tuple(await self.worker(self.listing, inode))
        handle = self.next_directory_handle
        self.next_directory_handle += 1
        self.directory_handles[handle] = rows
        return handle

    async def releasedir(self, fh):
        self.directory_handles.pop(fh,None)

    async def readdir(self, fh, start_id, token):
        # Bound the entire page, not merely each individual metadata HEAD.
        # The worker's abandoned thread remains limited and its curl has its
        # own hard transfer deadline; failure is surfaced rather than hidden.
        replied = False
        try:
            with trio.fail_after(DIRECTORY_TIMEOUT):
                rows = self.directory_handles.get(fh)
                if rows is None: raise pyfuse3.FUSEError(errno.EBADF)
                for index, (name, inode) in enumerate(rows, 1):
                    if index <= start_id:
                        continue
                    try:
                        attr = await self.getattr(inode)
                    except pyfuse3.FUSEError as error:
                        # Skip an unavailable original, but propagate timeouts/
                        # resource failures instead of retrying every next row.
                        if error.errno == errno.ETIMEDOUT and replied:
                            return
                        if error.errno != errno.ENOENT:
                            raise
                        continue
                    if not pyfuse3.readdir_reply(token, name.encode(), attr, index):
                        break
                    replied = True
        except trio.TooSlowError:
            # Preserve successful getdents progress; the next request resumes
            # at the last reply offset instead of restarting a slow page.
            if not replied:
                raise pyfuse3.FUSEError(errno.ETIMEDOUT)

    async def open(self, inode, flags, ctx=None):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC | os.O_CREAT):
            raise pyfuse3.FUSEError(errno.EROFS)
        node = self.nodes.get(inode)
        if not node or node.kind != 'file':
            raise pyfuse3.FUSEError(errno.EISDIR)
        await self.worker(self.api.size, node.row)
        handle=self.next_handle;self.next_handle+=1
        self.handles[handle]=node.row
        return pyfuse3.FileInfo(fh=handle, keep_cache=False)

    async def read(self, fh, off, size):
        if off < 0 or size < 0 or size > 1024**2:
            raise pyfuse3.FUSEError(errno.EINVAL)
        row=self.handles.get(fh)
        if row is None: raise pyfuse3.FUSEError(errno.EBADF)
        try:
            with trio.fail_after(30):
                return await self.worker(self.cache.read,row,off,size,time.monotonic()+24,limiter=self.read_limiter)
        except trio.TooSlowError:
            raise pyfuse3.FUSEError(errno.ETIMEDOUT)

    async def release(self, fh):
        self.handles.pop(fh,None)

    async def statfs(self, ctx=None):
        out = pyfuse3.StatvfsData()
        out.f_bsize = out.f_frsize = 4096
        out.f_blocks = self.cache.cap // 4096
        out.f_bfree = out.f_bavail = 0
        out.f_files = len(self.nodes)
        out.f_ffree = out.f_favail = 0
        out.f_namemax = 255
        return out

    async def write(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def create(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def mkdir(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def unlink(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def rmdir(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def rename(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def setattr(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def symlink(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def mknod(self, *args): raise pyfuse3.FUSEError(errno.EROFS)
    async def link(self, *args): raise pyfuse3.FUSEError(errno.EROFS)


# Codex review: this schema and account configuration remain example-only.
# No credential is included in this source package; use the private TTY prompt.
def keyring_key(store=None):
    import gi
    gi.require_version('Secret', '1')
    from gi.repository import Secret
    schema = Secret.Schema.new('org.example.ImmichFiles', Secret.SchemaFlags.NONE,
                              {'server': Secret.SchemaAttributeType.STRING, 'account': Secret.SchemaAttributeType.STRING})
    attributes = {'server': SERVER, 'account': ACCOUNT}
    if store is not None:
        return Secret.password_store_sync(schema, attributes, Secret.COLLECTION_DEFAULT, 'Immich Files read-only key', store, None)
    service = Secret.Service.get_sync(Secret.ServiceFlags.OPEN_SESSION, None)
    items = service.search_sync(schema, attributes, Secret.SearchFlags.ALL, None)
    if not items: return None
    if len(items) != 1 or items[0].get_locked():
        raise RuntimeError('Unlock or resolve duplicate Immich keyring entries before connecting')
    if not items[0].load_secret_sync(None): raise RuntimeError('Immich keyring item could not be unlocked or loaded')
    secret = items[0].get_secret()
    text=secret.get_text() if secret else None
    if not text:raise RuntimeError('Immich keyring item has no usable secret')
    return text


def mount():
    key = keyring_key()
    if not key:
        raise RuntimeError('Use connect-immich-files to enter the read-only key privately')
    api = API(key)
    mountpoint = Path(os.path.realpath(Path.home())) / 'Pictures' / 'Immich'
    import mount_support
    if mount_support.prepare_mountpoint(mountpoint, recover_while_active=True):
        raise RuntimeError('Mount point is not an empty private directory')
    filesystem = Filesystem(api, Cache(Path.home() / '.cache' / 'immich-files' / 'chunks', api))
    pyfuse3.init(filesystem, str(mountpoint), set(pyfuse3.default_options) | {'fsname=Immich', 'ro', 'nodev', 'nosuid', 'noexec'})
    try:
        trio.run(pyfuse3.main)
    finally:
        pyfuse3.close(unmount=True)


if __name__ == '__main__':
    try:
        mount()
    except KeyboardInterrupt:
        pass
    except Exception:
        print('Immich Files could not connect. Check the saved read-only key, Tailscale, and private mount directory.', file=__import__('sys').stderr)
        __import__('sys').exit(75)
