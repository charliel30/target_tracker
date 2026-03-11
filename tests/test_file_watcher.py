"""
test_file_watcher.py — File watcher integration test

Tests that dropping an article into the watch folder results in the system
correctly ingesting and storing the information. Designed to run against a
live Docker container.

Usage:
    python -m tests.test_file_watcher
    BASE_URL=http://host:port CONTAINER=target_tracker-target-tracker-1 python -m tests.test_file_watcher
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5050")
CONTAINER = os.environ.get("CONTAINER", "target_tracker-target-tracker-ephemeral-1")

ARTICLE_TEXT = """\
PARIS — French authorities confirmed Wednesday that 18 people were killed \
in a devastating bus crash on the A6 motorway south of Paris on the evening \
of November 12, 2025. The charter bus, carrying passengers from a corporate \
event, veered off an embankment and rolled multiple times before coming to \
rest in a ravine.

Among the dead was Nadia Volkov, 36, a Russian national who had been \
residing in Paris since early 2024. Volkov's body was identified through \
dental records after being recovered from the wreckage. She had no known \
next of kin in France.

Emergency services responded within minutes but were unable to save most \
of the passengers due to the severity of the impact. Seven others were \
hospitalized with critical injuries. French transport investigators have \
opened a formal inquiry into the cause of the accident.\
"""

_results = []


def _request(method, path, body=None, timeout=120):
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


def _chat(message):
    status, body = _request("POST", "/api/chat", {
        "message": message,
        "history": [],
    })
    assert status == 200, f"Chat request failed with status {status}"
    return body["response"]


def _docker_exec(cmd):
    """Run a command inside the Docker container."""
    result = subprocess.run(
        ["docker", "exec", CONTAINER] + cmd,
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _run_test(name, fn):
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

def test_article_ingestion_nadia_deceased():
    """
    Drop a news article about Nadia Volkov's death into the watch folder
    inside the container, wait for the file monitor to process it, then
    verify the system knows she is deceased.
    """
    # Step 1: Write the article into the container's watch folder
    print("\n    Writing article to container...", flush=True)
    rc, _, stderr = _docker_exec([
        "sh", "-c",
        f"cat > /tmp/news_articles/bus_crash_test.txt << 'ARTICLE_EOF'\n{ARTICLE_TEXT}\nARTICLE_EOF",
    ])
    assert rc == 0, f"Failed to write article to container: {stderr}"

    # Step 2: Verify the file exists in the container
    rc, stdout, _ = _docker_exec(["ls", "/tmp/news_articles/bus_crash_test.txt"])
    assert rc == 0, "Article file not found in container watch folder"

    # Step 3: Wait for the file monitor to pick it up (polls every 30s)
    print("    Waiting for file monitor to process (up to 90s)...", flush=True)
    start = time.time()
    processed = False
    while time.time() - start < 90:
        rc, stdout, _ = _docker_exec(["ls", "/tmp/news_articles/processed/bus_crash_test.txt"])
        if rc == 0:
            processed = True
            break
        time.sleep(5)

    assert processed, "File was not moved to processed/ within 90 seconds"
    print("    Article processed. Waiting for stores to finish writing...", flush=True)

    # Step 4: Wait for data to land in targets.json (embeddings + save are async)
    # Poll instead of sleeping a fixed amount
    events = []
    store_start = time.time()
    while time.time() - store_start < 30:
        rc, stdout, _ = _docker_exec([
            "python", "-c",
            "import json; f=open('data/targets.json'); d=json.load(f); "
            "events=d.get('Nadia Volkov',{}).get('major_events',[]); "
            "print(json.dumps(events))",
        ])
        if rc == 0:
            events = json.loads(stdout.strip())
            if any(e.get("event_type") == "death" for e in events):
                break
        time.sleep(3)

    # Step 5: Ask the system if Nadia Volkov is alive
    print("    Querying system about Nadia Volkov...", flush=True)
    resp = _chat("Is Nadia Volkov alive? Check major events.")
    resp_lower = resp.lower()

    assert any(kw in resp_lower for kw in ["deceased", "dead", "died", "death", "killed"]), (
        f"System should report Nadia Volkov as deceased after article ingestion.\n"
        f"  Response: {resp[:400]}"
    )

    # Step 6: Verify the major event is in the data stores
    print("    Verifying data stores...", flush=True)
    rc, stdout, _ = _docker_exec([
        "python", "-c",
        "import json; f=open('data/targets.json'); d=json.load(f); "
        "events=d.get('Nadia Volkov',{}).get('major_events',[]); "
        "print(json.dumps(events))",
    ])
    assert rc == 0, f"Failed to read targets.json in container"
    events = json.loads(stdout.strip())

    death_events = [e for e in events if e.get("event_type") == "death"]
    assert len(death_events) > 0, (
        f"No death major_event found in targets.json for Nadia Volkov.\n"
        f"  major_events: {events}"
    )
    assert "2025-11-12" in death_events[0].get("date", ""), (
        f"Death event should have date 2025-11-12, got: {death_events[0]}"
    )

    print(f"    Nadia Volkov correctly recorded as deceased (death on {death_events[0]['date']}).")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def wait_for_server(max_wait=120):
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
    print(f"  Target Tracker — File Watcher Integration Test")
    print(f"  Server: {BASE_URL}")
    print(f"  Container: {CONTAINER}")
    print(f"{'='*60}\n")

    if not wait_for_server():
        sys.exit(1)

    tests = [
        ("Article ingestion: Nadia deceased", test_article_ingestion_nadia_deceased),
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
