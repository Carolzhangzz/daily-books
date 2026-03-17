#!/usr/bin/env python3
"""Local bridge server for Daily Books. Calls Claude Code CLI to generate content."""
import http.server, json, subprocess, os, urllib.parse

PORT = 9527
DATA_DIR = os.path.expanduser("~/Documents/daily-books/data")

class Handler(http.server.BaseHTTPRequestHandler):
    def _respond(self, data, code=200):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _run_claude(self, prompt):
        try:
            subprocess.Popen(
                ["claude", "-p", prompt],
                cwd=os.path.expanduser("~/Documents/daily-books"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            print(f"Error launching claude: {e}")
            return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            self._respond({"ok": True})
            return

        if parsed.path == "/more":
            book = params.get("book", [""])[0]
            if not book:
                self._respond({"error": "missing book param"}, 400)
                return
            self._run_claude(f'/daily-books {book}')
            self._respond({"status": "generating", "book": book})
            return

        if parsed.path == "/generate":
            cats = params.get("cats", [""])[0]
            cmd = f'/daily-books {cats}'.strip() if cats else '/daily-books'
            self._run_claude(cmd)
            self._respond({"status": "generating", "cmd": cmd})
            return

        self._respond({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[bridge] {args[0]}")

if __name__ == "__main__":
    s = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Daily Books bridge running on http://127.0.0.1:{PORT}")
    s.serve_forever()
