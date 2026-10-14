"""Local diagnostic origin; no request logs or result persistence.

For iPhone/Tor, serve behind your own HTTPS reverse proxy on a public domain.
Do not expose this development server directly. Peer IP is the socket peer;
behind a reverse proxy it is NOT the browser IP. No forwarded headers trusted.
"""
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    def log_message(self, *args):
        pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        super().end_headers()
    def do_GET(self):
        if self.path.split('?')[0] == '/echo':
            data = json.dumps({'socketPeer': self.client_address[0],
                'userAgent': self.headers.get('User-Agent'),
                'acceptLanguage': self.headers.get('Accept-Language'),
                'clientHints': {k:v for k,v in self.headers.items() if k.lower().startswith('sec-ch-')},
                'note':'Behind a reverse proxy socketPeer is the proxy; verify IP at your TLS ingress.'}).encode()
            self.send_response(200); self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        else:
            super().do_GET()

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
