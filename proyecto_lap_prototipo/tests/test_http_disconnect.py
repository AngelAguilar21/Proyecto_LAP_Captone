import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_server import Handler
class ResponseTest(unittest.TestCase):
 def test_disconnects_are_ignored(self):
  for error in (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):
   handler=object.__new__(Handler)
   handler.send_response=lambda *a:None
   handler.send_header=lambda *a:None
   handler.end_headers=lambda:None
   class Closed:
    def write(self,data):raise error('connection closed')
   handler.wfile=Closed()
   handler.send_data(200,{'status':'running'})
 def test_unrelated_errors_remain_visible(self):
  handler=object.__new__(Handler)
  handler.send_response=lambda *a:None
  handler.send_header=lambda *a:None
  handler.end_headers=lambda:None
  class Broken:
   def write(self,data):raise OSError('unrelated')
  handler.wfile=Broken()
  with self.assertRaises(OSError):handler.send_data(200,{})
if __name__ == '__main__':
 unittest.main()
