#!/usr/bin/env python3
"""Private, user-initiated Immich connection. Never accepts credentials in argv."""
from pathlib import Path
from datetime import datetime
import errno
import getpass
import os
import shutil
import subprocess
import sys
import time
import mount_support
from immich_files import API,SERVER,keyring_key,asset_id,PAGE

HOME=Path(os.path.realpath(Path.home()))
MOUNT=HOME/'Pictures'/'Immich'
UNIT='immich-files.service'

def unit_active():
    return subprocess.run(['systemctl','--user','is-active','--quiet',UNIT],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode==0

def mount_record(timeout=2):
    return mount_support.mount_record(MOUNT,timeout=timeout)

def prepare_mountpoint(probe_timeout=2):
    return mount_support.prepare_mountpoint(MOUNT, active=unit_active,probe_timeout=probe_timeout)

def open_folder(path):
    # Opening the already-verified mount is best effort, independent of setup.
    opener = shutil.which('xdg-open')
    if not opener: return False
    try:
        subprocess.Popen([opener,str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False

def wait_until_ready(deadline):
    last_error=None
    while time.monotonic()<deadline:
        remaining=max(.01,deadline-time.monotonic())
        try:
            record=mount_record(timeout=min(2,remaining))
            if record:
                if len(record)!=2 or not record[0].startswith('fuse') or record[1]!='Immich':
                    raise RuntimeError('Another filesystem occupies the mount location')
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                if mount_support.probe_mount(MOUNT,timeout=min(2,remaining)):return
        except OSError as error:
            if error.errno not in (errno.ENOTCONN,errno.ESTALE,errno.ETIMEDOUT,errno.EIO):raise
            last_error=error
        remaining=deadline-time.monotonic()
        if remaining>0:time.sleep(min(.2,remaining))
    if last_error:raise last_error
    raise RuntimeError('The read-only mount did not become ready')

def validate(api):
    deadline=time.monotonic()+25
    albums=api.albums(deadline=deadline)
    rows,_=api.search({'visibility':{'eq':'timeline'}},deadline=deadline)
    # Search itself guarantees PAGE rows; retain that bound for injected APIs.
    for row in rows[:PAGE]:
        if time.monotonic()>=deadline:raise OSError(errno.ETIMEDOUT,'Validation deadline reached')
        row=dict(row);row['id']=asset_id(row['id']);size=api.size(row,deadline=deadline)
        if size==0:continue
        response=api.request('GET','/assets/'+row['id']+'/original',byte_range=(0,0),deadline=deadline)
        if response.status!=206 or response.headers.get('content-range')!=f'bytes 0-0/{size}' or len(response.body)!=1:
            raise RuntimeError('The server did not support bounded read-only downloads.')
        break
    return len(albums)

def bookmark():
    b=HOME/'.config'/'gtk-3.0'/'bookmarks'
    b.parent.mkdir(parents=True,exist_ok=True)
    text=b.read_text() if b.exists() else ''
    uri=MOUNT.as_uri();line=uri+' Immich Photos'
    if line not in text.splitlines():
        backups=HOME/'.local'/'share'/'immich-files'/'backups';backups.mkdir(parents=True,exist_ok=True,mode=0o700)
        if b.exists():shutil.copy2(b,backups/('gtk-bookmarks.'+datetime.now().strftime('%Y%m%d-%H%M%S')))
        lines=[x for x in text.splitlines() if x.split(' ',1)[0]!=uri]
        b.write_text('\n'.join(lines+[line])+'\n')

def main():
    if len(sys.argv)!=1:
        print('Run this helper without arguments. Enter the key privately when prompted.',file=sys.stderr);return 2
    needs_restart=False
    try:mounted=prepare_mountpoint()
    except mount_support.DisconnectedMountActive:
        mounted=False;needs_restart=True
    if mounted and not sys.stdin.isatty():
        bookmark();open_folder(MOUNT);return 0
    if not sys.stdin.isatty():
        print('Open Immich Files from the app launcher to connect privately.',file=sys.stderr);return 2
    print('Connect Immich Files (read-only)\n')
    key=keyring_key()
    fresh=not key
    if fresh:
        print('In Immich, open Account Settings → API Keys and create a key named Immich Files.')
        print('Select only: album.read, asset.read, asset.download.')
        print('Paste that key below. It stays hidden and is saved in your desktop keyring, not chat.\n')
        key=getpass.getpass('Immich read-only API key: ')
    replacement=False
    try:
        api=API(key)
    except ValueError:
        if fresh:raise
        replacement=True
    if not replacement:
        try:
            validate(api)
        except OSError as error:
            if fresh or error.errno != errno.EACCES:raise
            replacement=True
    if replacement:
        print('The saved read-only key was rejected. Enter a replacement privately.\n')
        key=getpass.getpass('Immich read-only API key: ')
        fresh=True
        api=API(key)
        validate(api)
    if fresh:
        if not keyring_key(store=key) or keyring_key()!=key:
            raise RuntimeError('Desktop keyring could not uniquely save the connection.')
    key=None
    if mounted and not fresh:
        bookmark();open_folder(MOUNT);return 0
    subprocess.run(['systemctl','--user','reset-failed',UNIT],check=True,timeout=10)
    subprocess.run(['systemctl','--user','enable',UNIT],check=True,timeout=45)
    # An already-running daemon holds its key in memory; replacement requires
    # restart, rather than enable --now which leaves that old process running.
    subprocess.run(['systemctl','--user','restart' if fresh or needs_restart else 'start',UNIT],check=True,timeout=45)
    # Observation only: startup cleanup belongs to the daemon, never polling.
    wait_until_ready(time.monotonic()+12)
    bookmark()
    print('\nConnected. Use Immich Photos in Files or the upload picker.')
    open_folder(MOUNT)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:sys.exit(130)
    except Exception:
        print('\nImmich Files is not connected. Check Tailscale, the read-only key permissions, and the private mount location.',file=sys.stderr)
        if sys.stdin.isatty():input('Press Enter to close.')
        sys.exit(75)
