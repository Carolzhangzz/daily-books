#!/usr/bin/env python3
"""Local bridge: serves static files + Claude CLI API for Daily Books."""
import http.server, json, subprocess, os, urllib.parse

PORT = 9527
ROOT = os.path.expanduser("~/Documents/daily-books")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # API routes
        if parsed.path == "/api/health":
            return self._json({"ok": True})

        if parsed.path == "/api/more":
            book = params.get("book", [""])[0]
            if not book:
                return self._json({"error": "missing book"}, 400)
            self._run_claude(f'/daily-books {book}')
            return self._json({"status": "generating", "book": book})

        if parsed.path == "/api/generate":
            cats = params.get("cats", [""])[0]
            cmd = f'/daily-books {cats}'.strip() if cats else '/daily-books'
            self._run_claude(cmd)
            return self._json({"status": "generating", "cmd": cmd})

        # Static files (index.html, data/*.json, etc.)
        super().do_GET()

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _run_claude(self, prompt):
        try:
            subprocess.Popen(
                ["claude", "-p", prompt],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[error] {e}")

    def log_message(self, fmt, *args):
        if '/api/' in str(args[0]):
            print(f"[api] {args[0]}")

if __name__ == "__main__":
    s = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"拾页 running at http://localhost:{PORT}")
    s.serve_forever()
