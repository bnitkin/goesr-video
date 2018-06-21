#!/usr/bin/python3 -u
# Simple HTTP server brings up the video and not much else.
from http.server  import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

import os, time, urllib
from http import HTTPStatus
from email.utils import parsedate

class ThreadingServer(ThreadingMixIn, HTTPServer):
    pass

class SimpleCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                             parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            # Support modified-since header (if provided)
            fs = os.fstat(f.fileno())
            modified = True
            if None != self.headers['If-Modified-Since']:
                modified = (int(fs.st_mtime) > time.mktime(parsedate(self.headers['If-Modified-Since'])))
                print('If-Modified-Since:', time.mktime(parsedate(self.headers['If-Modified-Since'])), int(fs.st_mtime), '(modified:', modified, ')' )
            self.send_response(HTTPStatus.OK if modified else HTTPStatus.NOT_MODIFIED)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.send_header("Cache-Control", "max-age=0, must-revalidate")
            self.end_headers()
            return f if modified else None
        except:
            f.close()
            raise

server_address = ('', 80)
SimpleCacheHTTPRequestHandler.extensions_map['webm'] = 'video/webm'
httpd = ThreadingServer(server_address, SimpleCacheHTTPRequestHandler)
print('Server is running')
httpd.serve_forever()
