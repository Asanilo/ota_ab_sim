import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .ota import OtaService


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/status", "/api/status"):
                self._send(200, service.status())
            elif path in ("/firmware", "/api/firmware"):
                self._send(200, service.list_firmware())
            else:
                self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            body = self._read_body()
            if path in ("/upgrade", "/api/upgrade"):
                name = body.get("firmware") or body.get("name")
                if not name:
                    self._send(400, {"ok": False, "error": "firmware is required"})
                    return
                result = service.upgrade(name)
                self._send(200 if result["ok"] else 400, result)
            elif path in ("/reboot", "/api/reboot"):
                result = service.reboot(bool(body.get("simulate_boot_failure", False)))
                self._send(200 if result["ok"] else 400, result)
            elif path in ("/reset", "/api/reset"):
                self._send(200, {"ok": True, "state": service.reset()})
            else:
                self._send(404, {"ok": False, "error": "not found"})

        def log_message(self, format, *args):
            return

        def _read_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw or "{}")

        def _send(self, status, payload):
            data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="OTA A/B simulator server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--base-dir", default=str(Path.cwd()))
    args = parser.parse_args(argv)

    service = OtaService(args.base_dir)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"Serving OTA simulator on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

