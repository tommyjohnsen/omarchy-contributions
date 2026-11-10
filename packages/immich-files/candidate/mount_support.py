# SPDX-License-Identifier: MIT
"""Bounded own-mount probing; never dereference a mounted leaf in the helper."""
import errno
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

class DisconnectedMountActive(RuntimeError):
    """A validated user connect may restart this unit; do not unmount it here."""

RESOLVE_PARENT_CODE = "import os,sys\nvalue=os.fsencode(os.path.join(os.path.realpath(os.path.dirname(sys.argv[1])),os.path.basename(sys.argv[1])))\nif not value.startswith(b'/') or len(value)>4096:sys.exit(5)\nos.write(1,value)\n"

def canonical_mount_path(path,timeout=2):
    # Parent resolution may itself enter a wedged remote filesystem. Isolate
    # it too; never call realpath on the leaf that may already be FUSE-mounted.
    process=subprocess.Popen([sys.executable,'-I','-c',RESOLVE_PARENT_CODE,str(path)],stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        try:code=process.wait(timeout=max(.01,timeout))
        except subprocess.TimeoutExpired:
            process.kill()
            try:process.wait(timeout=.5)
            except subprocess.TimeoutExpired:pass
            raise OSError(errno.ETIMEDOUT,'Immich parent resolution timed out')
        value=process.stdout.read(4097)
        if code or not value.startswith(b'/') or len(value)>4096:raise RuntimeError('Immich parent path could not be verified')
        return Path(os.fsdecode(value))
    finally:process.stdout.close()

def mount_record(path,timeout=2):
    path=canonical_mount_path(path,timeout)
    with open('/proc/self/mountinfo','rb') as table: raw=table.read(4*1024*1024+1)
    if not raw or len(raw)>4*1024*1024 or not raw.endswith(b'\n'):
        raise RuntimeError('Mount table unavailable or oversized')
    found=None
    for line in raw.split(b'\n')[:-1]:
        fields=line.split(b' ')
        if not line or any(not field for field in fields) or len(fields)<10 or b'-' not in fields[6:]:raise RuntimeError('Malformed mount table')
        separator=fields.index(b'-',6)
        if len(fields)-separator!=4 or not fields[0].isdigit() or not fields[1].isdigit() or not re.fullmatch(rb'[0-9]+:[0-9]+',fields[2]):raise RuntimeError('Malformed mount table')
        encoded=fields[4]
        if not encoded.startswith(b'/') or re.search(rb'\\(?!040|011|012|134)',encoded):raise RuntimeError('Malformed mountpoint')
        decoded=re.sub(rb'\\(040|011|012|134)',lambda m:bytes([int(m.group(1),8)]),encoded)
        if Path(os.fsdecode(decoded))==Path(path):found=[os.fsdecode(fields[separator+1]),os.fsdecode(fields[separator+2])]
    return found

PROBE_CODE = '''import errno,os,stat,sys
try:
 if stat.S_ISLNK(os.lstat(sys.argv[1]).st_mode):sys.exit(4)
 os.stat(sys.argv[1])
 with os.scandir(sys.argv[1]) as entries:next(entries,None)
except OSError as error:sys.exit(3 if error.errno in (errno.ENOTCONN,errno.ESTALE) else 5)
sys.exit(0)
'''

def probe_mount(path,timeout=2):
    """One isolated probe; timeout never waits indefinitely for an unkillable child."""
    process=subprocess.Popen([sys.executable,'-c',PROBE_CODE,str(path)],stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        code=process.wait(timeout=max(.01,timeout))
    except subprocess.TimeoutExpired:
        process.kill()
        try:process.wait(timeout=.5)
        except subprocess.TimeoutExpired:pass
        raise OSError(errno.ETIMEDOUT,'Immich mount responsiveness probe timed out')
    if code==0:return True
    if code==3:return False
    if code==4:raise RuntimeError('Mount location is a symlink; left unchanged')
    raise OSError(errno.EIO,'Immich mount responsiveness probe failed')

def prepare_mountpoint(path, *, active=lambda: False, recover_while_active=False,probe_timeout=2):
    path=canonical_mount_path(path,probe_timeout)
    record=mount_record(path,probe_timeout)
    own=bool(record and len(record)==2 and record[0].startswith('fuse') and record[1]=='Immich')
    if record and not own:raise RuntimeError('Another filesystem occupies the mount location; left unchanged')
    if own:
        if probe_mount(path,probe_timeout):return True
        if active() and not recover_while_active:raise DisconnectedMountActive('Disconnected own mount requires authenticated restart')
        subprocess.run(['fusermount3','-u',str(path)],check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if mount_record(path):raise RuntimeError('Disconnected mount remained mounted')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise RuntimeError('Mount location must be an owned private directory')
    if any(path.iterdir()):raise RuntimeError('Mount location contains files; left unchanged')
    return False
