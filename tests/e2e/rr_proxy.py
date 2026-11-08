"""Round-robin HTTP proxy (stdlib only) that simulates Vercel's many function instances.

Every request goes to the next backend in turn, so in-memory state that lives in one
process is visible only on some requests. A dead backend gives a 502 (like losing an instance).

    python tests/e2e/rr_proxy.py --port 8000 --backends 127.0.0.1:8001,127.0.0.1:8002
"""
from __future__ import annotations

import argparse
import http.client
import itertools
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
       "proxy-authorization", "proxy-authenticate", "host", "content-length"}


def make_handler(backends):
    cycle = itertools.cycle(backends)
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):      # one line per request, with the backend used
            pass

        def _proxy(self):
            with lock:
                target = next(cycle)
            host, port = target.split(":")
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            try:
                c = http.client.HTTPConnection(host, int(port), timeout=120)
                c.request(self.command, self.path, body=body, headers=headers)
                r = c.getresponse()
                data = r.read()
                status, rh = r.status, r.getheaders()
                c.close()
            except OSError as e:
                status, rh, data = 502, [("Content-Type", "text/plain")], f"backend {target} down: {e}".encode()
            self.send_response(status)
            for k, v in rh:
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("X-RR-Backend", target)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            print(f"{self.command} {self.path} -> {target} {status}", flush=True)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _proxy

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--backends", default="127.0.0.1:8001,127.0.0.1:8002")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.backends.split(",")))
    print(f"rr_proxy on 127.0.0.1:{a.port} -> {a.backends}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
