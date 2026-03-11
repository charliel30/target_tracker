"""
test_functional.py — Functional tests for Target Tracker

Runs against a live server (default http://localhost:5000).
Tests the Flask API endpoints with real LLM calls.

Usage:
    python -m tests.test_functional              # default localhost:5000
    BASE_URL=http://host:port python -m tests.test_functional
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

# Track results
_results = []


def _request(method, path, body=None, timeout=120):
    """Make an HTTP request and return (status_code, parsed_json_or_text)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def _run_test(name, fn):
    """Run a test function, record pass/fail."""
    print(f"  [{name}] ", end="", flush=True)
    try:
        fn()
        print("PASS")
        _results.append((name, True, None))
    except Exception as e:
        print(f"FAIL — {e}")
        _results.append((name, False, str(e)))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_index_page():
    """GET / returns the HTML UI."""
    status, body = _request("GET", "/")
    assert status == 200, f"Expected 200, got {status}"
    assert "TARGET TRACKER" in body.upper() or "target" in body.lower(), \
        "Index page doesn't contain expected content"


def test_alerts_endpoint():
    """GET /api/alerts returns a JSON list."""
    status, body = _request("GET", "/api/alerts")
    assert status == 200, f"Expected 200, got {status}"
    assert isinstance(body, list), f"Expected list, got {type(body).__name__}"


def test_chat_list_targets():
    """POST /api/chat — ask to list targets."""
    status, body = _request("POST", "/api/chat", {
        "message": "List all the target names you know about.",
        "history": [],
    })
    assert status == 200, f"Expected 200, got {status}"
    assert "response" in body, f"Missing 'response' key in body"
    resp = body["response"].lower()
    # Should mention at least one target from the data
    assert "viktor" in resp or "petrov" in resp or "target" in resp, \
        f"Response doesn't seem to list targets: {body['response'][:200]}"


def test_chat_target_lookup():
    """POST /api/chat — ask about a specific target."""
    status, body = _request("POST", "/api/chat", {
        "message": "What do you know about Viktor Petrov?",
        "history": [],
    })
    assert status == 200, f"Expected 200, got {status}"
    resp = body["response"].lower()
    # Should contain some info about Viktor Petrov
    assert any(kw in resp for kw in ["petrov", "moscow", "person", "scar", "location"]), \
        f"Response doesn't contain expected Viktor Petrov info: {body['response'][:200]}"


def test_chat_distance_calculation():
    """POST /api/chat — ask for distance between two targets."""
    status, body = _request("POST", "/api/chat", {
        "message": "What is the distance between Viktor Petrov and Nadia Volkov?",
        "history": [],
    })
    assert status == 200, f"Expected 200, got {status}"
    resp = body["response"].lower()
    assert "km" in resp or "distance" in resp or "kilometer" in resp, \
        f"Response doesn't contain distance info: {body['response'][:200]}"


def test_chat_conversation_history():
    """POST /api/chat — verify conversation history is used."""
    # First message
    status1, body1 = _request("POST", "/api/chat", {
        "message": "Who is Viktor Petrov?",
        "history": [],
    })
    assert status1 == 200, f"First message failed with {status1}"

    # Follow-up using history
    status2, body2 = _request("POST", "/api/chat", {
        "message": "What are his associations?",
        "history": [
            {"role": "user", "content": "Who is Viktor Petrov?"},
            {"role": "assistant", "content": body1["response"]},
        ],
    })
    assert status2 == 200, f"Follow-up failed with {status2}"
    resp = body2["response"].lower()
    # Should understand "his" refers to Viktor Petrov from history
    assert any(kw in resp for kw in ["association", "nadia", "volkov", "sedan", "kremlin"]), \
        f"Follow-up doesn't seem to use history context: {body2['response'][:200]}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def wait_for_server(max_wait=120):
    """Wait for the server to become available."""
    print(f"Waiting for server at {BASE_URL}...", flush=True)
    start = time.time()
    while time.time() - start < max_wait:
        try:
            _request("GET", "/", timeout=5)
            print("Server is up!")
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(2)
    print("Server did not become available in time.")
    return False


def main():
    print(f"\n{'='*60}")
    print(f"  Target Tracker — Functional Tests")
    print(f"  Server: {BASE_URL}")
    print(f"{'='*60}\n")

    if not wait_for_server():
        sys.exit(1)

    tests = [
        ("Index page loads", test_index_page),
        ("Alerts endpoint", test_alerts_endpoint),
        ("Chat: list targets", test_chat_list_targets),
        ("Chat: target lookup", test_chat_target_lookup),
        ("Chat: distance calc", test_chat_distance_calculation),
        ("Chat: conversation history", test_chat_conversation_history),
    ]

    for name, fn in tests:
        _run_test(name, fn)

    # Summary
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(_results)}")
    print(f"{'='*60}\n")

    if failed:
        print("Failed tests:")
        for name, ok, err in _results:
            if not ok:
                print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
