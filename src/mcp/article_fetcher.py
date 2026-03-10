"""
article_fetcher.py — MCP-style module for fetching articles from a REST URL.

MCP (Model Context Protocol) is a standard for exposing tools to LLM agents.
This module can be used two ways:
  1. Direct import: call fetch_articles(url) from within the app.
  2. Standalone MCP server: python -m src.mcp.article_fetcher
     Reads JSON-RPC requests from stdin, writes responses to stdout.
"""

import json
import sys
import urllib.request
import urllib.error

from src.logging_config import get_agent_logger

log = get_agent_logger("MCP")


def fetch_articles(url: str) -> list:
    """
    Fetch a list of articles from a REST endpoint via HTTP GET.

    Expects the response to be a JSON array of objects, each with at least
    a "content" field. Optional fields: "title", "date", "source".

    Returns an empty list on any error so callers never crash.
    """
    log.info(f"Fetching articles from {url}")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        log.warning(f"Could not reach {url}: {e}")
        return []
    except Exception as e:
        log.warning(f"Unexpected error fetching {url}: {e}")
        return []

    try:
        articles = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"Bad JSON from {url}: {e}")
        return []

    if not isinstance(articles, list):
        log.warning(f"Expected a JSON array from {url}, got {type(articles).__name__}")
        return []

    log.info(f"Fetched {len(articles)} article(s) from {url}")
    return articles


# ---------------------------------------------------------------------------
# Minimal MCP stdin/stdout server — for teaching what MCP looks like.
# Each request is a JSON-RPC 2.0 object; we support one method: fetch_articles.
# Run with:  python -m src.mcp.article_fetcher
# ---------------------------------------------------------------------------

def _handle_request(req: dict) -> dict:
    """Dispatch a single JSON-RPC request and return the response dict."""
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "fetch_articles":
        url = params.get("url", "")
        result = fetch_articles(url)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


if __name__ == "__main__":
    log.info("MCP article_fetcher server started (stdin/stdout JSON-RPC)")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        else:
            resp = _handle_request(req)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
