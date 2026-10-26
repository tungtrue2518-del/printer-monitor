"""Small web dashboard + JSON API, standard library only.

    GET  /              dashboard page
    GET  /api/status    latest poll of every printer
    GET  /api/usage     pages per day / month and toner forecasts
    POST /api/refresh   poll now instead of waiting for the next round
"""
import datetime
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import monitor
from .history import History

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


class State:
    def __init__(self, cfg, history_path):
        self.cfg = cfg
        self.history = History(history_path)
        self.lock = threading.Lock()
        self.printers = {}
        self.updated_at = None
        self.wake = threading.Event()

    def poll(self):
        result = monitor.poll_all(self.cfg["printers"], self.cfg["community"])
        with self.lock:
            self.printers = result
            self.updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            self.history.record(result)
        except OSError as exc:                       # history is a bonus - never break live status
            print(f"[history] save failed: {exc!r}", flush=True)

    def loop(self):
        while True:
            self.poll()
            self.wake.wait(self.cfg["pollSeconds"])
            self.wake.clear()

    def status(self):
        with self.lock:
            printers = [self.printers[p["ip"]] for p in self.cfg["printers"] if p["ip"] in self.printers]
            updated = self.updated_at
        needing = [p for p in printers if p["attention"]["level"] != "ok"]
        return {"updatedAt": updated, "printers": printers,
                "summary": {"total": len(printers), "online": sum(p["online"] for p in printers),
                            "needingAttention": len(needing),
                            "critical": sum(p["attention"]["level"] == "critical" for p in printers)}}

    def usage(self):
        with self.lock:
            live = dict(self.printers)
        return self.history.report(self.cfg["printers"], live)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code=200):
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                with open(PAGE, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._json(state.status())
            elif path == "/api/usage":
                self._json(state.usage())
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path.split("?")[0] == "/api/refresh":
                state.poll()
                self._json(state.status())
            else:
                self._json({"error": "not found"}, 404)

        def log_message(self, *args):
            pass

    return Handler


def serve(cfg, config_path, host="127.0.0.1", port=8080):
    history_path = cfg.get("historyFile") or os.path.join(os.path.dirname(os.path.abspath(config_path)), "printer_history.json")
    state = State(cfg, history_path)
    threading.Thread(target=state.loop, daemon=True).start()
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print(f"Printer monitor on http://{host}:{port}  ({len(cfg['printers'])} printers, every {cfg['pollSeconds']}s)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
