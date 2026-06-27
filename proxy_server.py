#!/usr/bin/env python3
import http.server
import urllib.request
import urllib.error
import json
import os

TOKEN = 'c1c2310c-c93c-4ff1-b969-a60f41d477dc'
API_BASE = 'https://mcassessor.maricopa.gov'
PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/') or self.path.startswith('/api?'):
            self._proxy()
        else:
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _proxy(self):
        upstream = API_BASE + self.path[4:]  # strip /api
        req = urllib.request.Request(upstream, headers={
            'AUTHORIZATION': TOKEN,
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')

    def log_message(self, fmt, *args):
        print(f'{self.address_string()} {fmt % args}')


if __name__ == '__main__':
    os.chdir('/home/user/Sacred-mirror')
    with http.server.HTTPServer(('0.0.0.0', PORT), Handler) as httpd:
        print(f'Proxy running on http://localhost:{PORT}')
        print(f'Open: http://localhost:{PORT}/land-finder.html')
        httpd.serve_forever()
