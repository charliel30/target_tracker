"""
article_server.py — Simple REST server that serves articles from a folder.

Reads .txt files from a configurable directory and returns them as a JSON
array via GET /articles. After serving, files are moved to a processed/
subfolder so they aren't returned again.

Usage:
    python tests/article_server.py                          # defaults: /tmp/article_inbox, port 6000
    ARTICLE_DIR=/path/to/folder PORT=6000 python tests/article_server.py

Response format (matches what src/mcp/article_fetcher.py expects):
    [
      {"title": "filename.txt", "content": "full article text...", "date": "2026-03-10"},
      ...
    ]

Docker:
    This runs as a second container alongside the main app. See docker-compose.yml
    for the article-server service definition. Drop .txt files into the mounted
    host folder (default: /tmp/article_inbox) and hit GET /articles to retrieve them.
"""

import json
import os
import shutil
from datetime import date
from http.server import HTTPServer, BaseHTTPRequestHandler


ARTICLE_DIR = os.environ.get("ARTICLE_DIR", "/tmp/article_inbox")
PORT = int(os.environ.get("PORT", "6000"))


class ArticleHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/articles":
            self._serve_articles()
        elif self.path == "/":
            self._health()
        else:
            self.send_error(404)

    def _health(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def _serve_articles(self):
        """Read all .txt files, return as JSON list, move to processed/."""
        os.makedirs(ARTICLE_DIR, exist_ok=True)
        processed_dir = os.path.join(ARTICLE_DIR, "processed")
        os.makedirs(processed_dir, exist_ok=True)

        articles = []

        try:
            entries = sorted(os.listdir(ARTICLE_DIR))
        except OSError as exc:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode())
            return

        for filename in entries:
            filepath = os.path.join(ARTICLE_DIR, filename)
            if not os.path.isfile(filepath):
                continue
            if filename.startswith("."):
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue

            if not content.strip():
                continue

            articles.append({
                "title": filename,
                "content": content,
                "date": date.today().isoformat(),
            })

            # Move to processed
            try:
                shutil.move(filepath, os.path.join(processed_dir, filename))
            except OSError as exc:
                print(f"Warning: could not move {filename} to processed/: {exc}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(articles, indent=2).encode())

        print(f"Served {len(articles)} article(s), moved to processed/")

    def log_message(self, format, *args):
        """Override to add prefix."""
        print(f"[ArticleServer] {args[0]}")


def main():
    os.makedirs(ARTICLE_DIR, exist_ok=True)
    print(f"[ArticleServer] Serving articles from: {ARTICLE_DIR}")
    print(f"[ArticleServer] Listening on port {PORT}")
    print(f"[ArticleServer] GET /articles  — fetch and consume articles")
    print(f"[ArticleServer] GET /          — health check")

    server = HTTPServer(("0.0.0.0", PORT), ArticleHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
