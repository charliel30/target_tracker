"""
server.py — Flask web server

Serves the UI and exposes a small REST API for the chat interface and
alert management.  All async agent calls are bridged via asyncio.run().
"""

import asyncio

from flask import Flask, jsonify, request, send_from_directory

from src.agents.anomaly_detector import dismiss_alert, get_alerts
from src.agents.orchestrator import handle_user_message
from src.logging_config import get_agent_logger

log = get_agent_logger("Server")

import os

# static/ lives at the project root, one level up from src/
_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app = Flask(__name__, static_folder=_STATIC_DIR)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main UI."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static assets (JS, CSS, etc.)."""
    return send_from_directory(app.static_folder, filename)


# ---------------------------------------------------------------------------
# Chat API
# ---------------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Receive a user message and return the orchestrator's response.

    Request body:  {"message": str, "history": [{"role": ..., "content": ...}]}
    Response body: {"response": str, "new_alerts": list}
    """
    data = request.get_json(force=True)
    message: str = data.get("message", "")
    history: list = data.get("history", [])

    log.info(f"POST /api/chat — message: {message[:80]!r}{'...' if len(message) > 80 else ''}")

    # Bridge the async orchestrator into this sync Flask route
    result = asyncio.run(handle_user_message(message, history))

    return jsonify(result)


# ---------------------------------------------------------------------------
# Alert API
# ---------------------------------------------------------------------------

@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    """Return all current anomaly alerts."""
    return jsonify(get_alerts())


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id: str):
    """Dismiss (delete) a specific alert by its ID."""
    removed = dismiss_alert(alert_id)
    if removed:
        log.info(f"DELETE /api/alerts/{alert_id} — dismissed")
        return jsonify({"success": True})
    else:
        log.warning(f"DELETE /api/alerts/{alert_id} — not found")
        return jsonify({"success": False, "error": "Alert not found"}), 404


# ---------------------------------------------------------------------------
# Server startup helper (called by main.py)
# ---------------------------------------------------------------------------

def run_server(host: str, port: int) -> None:
    """Start the Flask development server."""
    log.info(f"Starting Flask server on {host}:{port}")
    # debug=False keeps Flask from spawning a reloader thread that conflicts
    # with the background file-monitor thread started in main.py
    app.run(host=host, port=port, debug=False)
