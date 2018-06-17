#!/usr/bin/python3 -u
# Simple HTTP server brings up the video and not much else.
from http.server  import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

class ThreadingServer(ThreadingMixIn, HTTPServer):
        pass

server_address = ('', 80)
httpd = ThreadingServer(server_address, SimpleHTTPRequestHandler)
print('Server is running')
httpd.serve_forever()
