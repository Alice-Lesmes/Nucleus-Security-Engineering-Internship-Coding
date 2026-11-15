"""Tiny HTTP backend for the calculator front-end (standard library only).

POST /api/calculate  {"expression": "1+2*3"}  ->  {"result": "7"}  or  {"error": "..."}
Run:  python server.py   (listens on http://localhost:8000)
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from calculator import CalcError, calculate

HOST, PORT = "127.0.0.1", 8000


def format_result(value) -> str:
    # Tidy float noise (0.1+0.2 -> 0.3) and send as a string so big ints keep precision in JS.
    if isinstance(value, float):
        value = float(f"{value:.12g}")
        if value.is_integer():
            value = int(value)
    return str(value)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/calculate":
            return self._send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            expression = json.loads(self.rfile.read(length))["expression"]
            if not isinstance(expression, str) or len(expression) > 500:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return self._send(400, {"error": "Bad request"})
        try:
            self._send(200, {"result": format_result(calculate(expression))})
        except CalcError as e:
            self._send(200, {"error": str(e)})
        except RecursionError:
            self._send(200, {"error": "Expression too complex"})

    def log_message(self, fmt, *args):
        pass  # keep the console quiet


if __name__ == "__main__":
    print(f"Calculator backend running on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
