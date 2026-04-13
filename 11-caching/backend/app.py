"""Simulated slow database backend for the caching lab.

Serves product data with an artificial delay to make cache speedup
measurable. Supports GET (read) and PUT (update) operations.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

DELAY_SECONDS = 0.5

products = {
    str(i): {
        "id": i,
        "name": f"Product {i}",
        "price": round(9.99 + (i * 1.5), 2),
        "category": ["Electronics", "Books", "Clothing", "Food", "Sports"][i % 5],
        "stock": 100 + (i * 3),
    }
    for i in range(1, 101)
}


class ProductHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "products":
            product_id = parts[1]
            if product_id in products:
                time.sleep(DELAY_SECONDS)
                self._send_json(200, products[product_id])
            else:
                self._send_json(404, {"error": "Product not found"})
        elif len(parts) == 1 and parts[0] == "health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_PUT(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "products":
            product_id = parts[1]
            if product_id in products:
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, ValueError):
                    self._send_json(400, {"error": "Invalid JSON body"})
                    return
                products[product_id].update(body)
                time.sleep(DELAY_SECONDS)
                self._send_json(200, products[product_id])
            else:
                self._send_json(404, {"error": "Product not found"})
        else:
            self._send_json(404, {"error": "Not found"})

    def _send_json(self, code, data):
        response = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, fmt, *args):  # noqa: ARG002
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), ProductHandler)
    print("Backend database running on port 5000 (500ms delay per request)")
    server.serve_forever()
