# SPDX-License-Identifier: MIT
"""Hard process-pipe limits independent of curl's own filesize/version behavior."""
import errno
import os
import selectors
import subprocess
import time

def run(args, *, input, timeout, env, output_limit, stderr_limit=64*1024):
    if not isinstance(input,bytes) or len(input)>64*1024:
        raise ValueError('Curl configuration exceeds limit')
    process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    selector=selectors.DefaultSelector()
    deadline=time.monotonic()+timeout
    sent=0;output=bytearray();errors=0
    try:
        for stream,event,name in [(process.stdin,selectors.EVENT_WRITE,'stdin'),(process.stdout,selectors.EVENT_READ,'stdout'),(process.stderr,selectors.EVENT_READ,'stderr')]:
            os.set_blocking(stream.fileno(),False)
            selector.register(stream,event,name)
        while selector.get_map():
            remaining=deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(args,timeout)
            events=selector.select(remaining)
            if not events:raise subprocess.TimeoutExpired(args,timeout)
            for key,_ in events:
                if key.data=='stdin':
                    try:sent+=os.write(key.fd,input[sent:])
                    except BlockingIOError:continue
                    except BrokenPipeError:sent=len(input)
                    if sent==len(input):
                        selector.unregister(key.fileobj);key.fileobj.close()
                    continue
                try:chunk=os.read(key.fd,65536)
                except BlockingIOError:continue
                if not chunk:
                    selector.unregister(key.fileobj);continue
                if key.data=='stdout':
                    if len(output)+len(chunk)>output_limit:
                        raise OSError(errno.EOVERFLOW,'Curl response exceeds hard pipe limit')
                    output.extend(chunk)
                else:
                    errors+=len(chunk)
                    if errors>stderr_limit:raise OSError(errno.EOVERFLOW,'Curl diagnostic limit reached')
        code=process.wait(timeout=max(0,deadline-time.monotonic()))
        return subprocess.CompletedProcess(args,code,bytes(output),b'')
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        for stream in [process.stdin,process.stdout,process.stderr]:
            if not stream.closed:stream.close()
