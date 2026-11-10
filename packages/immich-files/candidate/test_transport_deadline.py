# Temporary loopback servers serve only public fixture bytes and fake credentials.
import errno,socketserver,subprocess,threading,time,unittest
from immich_files import API, SERVER

class Fixture(socketserver.BaseRequestHandler):
 def handle(self):
  self.request.recv(8192)
  try:
   if self.server.mode=='headers':
    for byte in b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n':
     self.request.sendall(bytes([byte]));time.sleep(.04)
   else:
    self.request.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n')
    for _ in range(100):self.request.sendall(b'x');time.sleep(.08)
  except OSError:pass
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True
class DeadlineTest(unittest.TestCase):
 def test_slow_headers_and_body_are_hard_bounded(self):
  for mode in ('headers','body'):
   with self.subTest(mode=mode):
    server=Server(('127.0.0.1',0),Fixture);server.mode=mode
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def runner(args,**kwargs):
     # Replace only the fixture transport origin; no real server is contacted.
     kwargs['input']=kwargs['input'].replace(SERVER.encode(),f'http://127.0.0.1:{server.server_address[1]}'.encode())
     return subprocess.run(args,**kwargs)
    start=time.monotonic()
    try:
     with self.assertRaises(OSError)as caught:API('public-fake-test-key',runner).request('GET','/albums',deadline=start+.35)
     self.assertEqual(caught.exception.errno,errno.ETIMEDOUT)
     self.assertLess(time.monotonic()-start,1.5)
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':unittest.main()
