"""Backend service for the proxies lab.

One image runs as two services (users and orders). Every response reports
what the service saw about the request: the TCP peer that connected to it
and the forwarding headers a proxy may have added. Each request is also
logged to stdout so students can compare the before and after of a proxy.
"""

import json
import os
import socket
import sys
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE = os.environ.get("SERVICE_NAME", "backend")
PORT = int(os.environ.get("PORT", "5000"))
REPORT_DELAY = float(os.environ.get("REPORT_DELAY_SECONDS", "1.5"))
HOSTNAME = socket.gethostname()


class Handler(BaseHTTPRequestHandler):
    server_version = "PythonBackend/1.0"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send_json(200, {"status": "ok"}, log=False)
            return
        body = {
            "service": SERVICE,
            "instance": HOSTNAME,
            "path_seen": self.path,
            "client_ip_seen": self.client_address[0],
            "host_header": self.headers.get("Host", "-"),
            "x_forwarded_for": self.headers.get("X-Forwarded-For", "-"),
            "x_forwarded_proto": self.headers.get("X-Forwarded-Proto", "-"),
            "x_real_ip": self.headers.get("X-Real-IP", "-"),
        }
        if path == "/report":
            # Simulates an expensive query, so a cache in the proxy is measurable.
            time.sleep(REPORT_DELAY)
            body["report"] = "daily summary"
            body["generated_at"] = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        self._send_json(200, body)

    def _send_json(self, code, data, log=True):
        payload = (json.dumps(data, indent=2) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Powered-By", f"python/{SERVICE}")
        self.end_headers()
        self.wfile.write(payload)
        if log:
            print(
                f"{SERVICE} {self.command} {self.path} "
                f"client={self.client_address[0]} "
                f"xff={self.headers.get('X-Forwarded-For', '-')} "
                f"proto={self.headers.get('X-Forwarded-Proto', '-')} "
                f"host={self.headers.get('Host', '-')}",
                flush=True,
            )

    def log_message(self, fmt, *args):  # noqa: ARG002
        pass


if __name__ == "__main__":
    print(f"{SERVICE} listening on port {PORT}", file=sys.stderr, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
