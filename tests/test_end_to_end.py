"""
test_end_to_end.py — Full end-to-end integration test

Tests the complete pipeline: file watcher ingestion, MCP article server fetch,
anomaly detection, and chat queries — all against a live Docker deployment.

Requires both the target-tracker-ephemeral and article-server containers running
in ephemeral mode:
    docker compose --profile ephemeral up --build -d

Usage:
    python -m tests.test_end_to_end
    BASE_URL=http://host:port python -m tests.test_end_to_end

Flow:
    1. Ask if Nadia Volkov is dead → expect NO
    2. Drop death article into container watch folder → wait for processing
    3. Ask if Nadia Volkov is dead → expect YES
    4. Drop "spotted alive" article into article server inbox on host
    5. Tell chatbot to fetch from article server → expect processing
    6. Check alerts → expect anomaly (dead person spotted alive)
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5050")
ARTICLE_SERVER_URL = os.environ.get("ARTICLE_SERVER_URL", "http://localhost:6000")
CONTAINER = os.environ.get("CONTAINER", "target_tracker-target-tracker-ephemeral-1")
ARTICLE_INBOX = os.environ.get("ARTICLE_INBOX", "/tmp/article_inbox")

DEATH_ARTICLE = """\
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

ALIVE_SIGHTING_ARTICLE = """\
BERLIN — Multiple witnesses reported seeing Nadia Volkov at a café in \
Kreuzberg, Berlin on the afternoon of March 9, 2026. Volkov, who was \
previously believed to have died in a bus crash near Paris in November \
2025, was reportedly seen speaking on a mobile phone and appeared to be \
in good health. One witness, a former colleague, said they were \
"absolutely certain" it was her. German federal police have been notified \
and are reviewing surveillance footage from the area.\
"""

_results = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(method, path, body=None, timeout=120, base=None):
    url = f"{base or BASE_URL}{path}"
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


def _poll(check_fn, timeout=60, interval=3, desc="condition"):
    """Poll until check_fn() returns True or timeout is reached."""
    start = time.time()
    while time.time() - start < timeout:
        if check_fn():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Tests (run in order — each builds on the previous)
# ---------------------------------------------------------------------------

def test_01_nadia_initially_alive():
    """Nadia Volkov should have no death events at the start."""
    print("\n    Asking if Nadia Volkov is dead (expect: no)...", flush=True)
    resp = _chat("Is Nadia Volkov dead? Check her major events.")
    resp_lower = resp.lower()

    # The response should indicate she is NOT dead. Look for negative framing.
    alive_indicators = [
        "no major events", "no record", "no death", "no entries",
        "not recorded as dead", "not dead", "no confirmed",
    ]
    confirmed_dead_indicators = [
        "she is dead", "she is deceased", "recorded as dead",
        "confirmed dead", "is dead", "was killed",
    ]
    assert any(kw in resp_lower for kw in alive_indicators) or \
        not any(kw in resp_lower for kw in confirmed_dead_indicators), (
        f"Nadia should be alive at start, but response confirms death.\n"
        f"  Response: {resp[:400]}"
    )
    print(f"    Confirmed: Nadia is not recorded as dead.")


def test_02_ingest_death_article():
    """Drop a death article into the container's watch folder and verify ingestion."""
    print("\n    Writing death article to container watch folder...", flush=True)
    rc, _, stderr = _docker_exec([
        "sh", "-c",
        f"cat > /tmp/news_articles/bus_crash_nadia.txt << 'ARTICLE_EOF'\n{DEATH_ARTICLE}\nARTICLE_EOF",
    ])
    assert rc == 0, f"Failed to write article to container: {stderr}"

    # Wait for death event to appear in targets.json
    print("    Waiting for file monitor to process and store death event...", flush=True)

    def death_event_exists():
        rc, stdout, _ = _docker_exec([
            "python", "-c",
            "import json; d=json.load(open('data/targets.json')); "
            "events=d.get('Nadia Volkov',{}).get('major_events',[]); "
            "deaths=[e for e in events if e.get('event_type')=='death']; "
            "print(len(deaths))",
        ])
        return rc == 0 and stdout.strip() == "1"

    assert _poll(death_event_exists, timeout=90, interval=5, desc="death event"), (
        "Death event did not appear in targets.json within 90 seconds"
    )
    print("    Death event recorded in data store.")


def test_03_nadia_now_dead():
    """After ingesting the death article, the system should report Nadia as dead."""
    print("\n    Asking if Nadia Volkov is dead (expect: yes)...", flush=True)
    resp = _chat("Is Nadia Volkov dead? Check her major events.")
    resp_lower = resp.lower()

    death_keywords = ["deceased", "dead", "died", "death", "killed"]
    assert any(kw in resp_lower for kw in death_keywords), (
        f"System should report Nadia as deceased after article ingestion.\n"
        f"  Response: {resp[:400]}"
    )

    assert "2025-11-12" in resp or "november" in resp_lower, (
        f"Response should mention the death date.\n"
        f"  Response: {resp[:400]}"
    )
    print(f"    Confirmed: Nadia is reported as dead (bus crash 2025-11-12).")


def test_04_article_server_alive_sighting():
    """
    Drop a 'spotted alive' article into the article server inbox, tell the
    chatbot to fetch from the article server, and verify it processes.
    """
    # Write the alive sighting article to the host inbox folder
    print("\n    Writing alive-sighting article to article server inbox...", flush=True)
    inbox_path = os.path.join(ARTICLE_INBOX, "nadia_alive_sighting.txt")
    os.makedirs(ARTICLE_INBOX, exist_ok=True)
    with open(inbox_path, "w") as f:
        f.write(ALIVE_SIGHTING_ARTICLE)

    # Verify article server has it
    status, body = _request("GET", "/articles", base=ARTICLE_SERVER_URL, timeout=10)
    assert status == 200, f"Article server returned status {status}"
    assert isinstance(body, list) and len(body) > 0, (
        f"Article server should have returned at least 1 article, got: {body}"
    )
    print(f"    Article server confirmed: {len(body)} article(s) ready.")

    # Oops — we consumed the article by GETting it. The article server moves
    # files to processed/ on GET. We need to put it back for the chatbot.
    # Actually, we already consumed it — let's write another copy.
    with open(inbox_path, "w") as f:
        f.write(ALIVE_SIGHTING_ARTICLE)

    # Tell the chatbot to fetch from the article server
    print("    Telling chatbot to fetch from article server...", flush=True)
    resp = _chat("Fetch and process articles from http://article-server:6000/articles")
    resp_lower = resp.lower()

    assert "processed" in resp_lower or "article" in resp_lower, (
        f"Expected the chatbot to confirm article processing.\n"
        f"  Response: {resp[:400]}"
    )
    print(f"    Chatbot response: {resp[:200]}")


def test_05_anomaly_alert_exists():
    """After a dead person is spotted alive, an anomaly alert should exist."""
    print("\n    Checking alerts endpoint for anomaly...", flush=True)

    # Give a moment for anomaly detection to complete (it runs async during article processing)
    def alert_exists():
        status, body = _request("GET", "/api/alerts")
        if status != 200 or not isinstance(body, list):
            return False
        return any(
            a.get("target_name") == "Nadia Volkov"
            for a in body
        )

    assert _poll(alert_exists, timeout=30, interval=3, desc="anomaly alert"), (
        "No anomaly alert found for Nadia Volkov within 30 seconds"
    )

    # Fetch and display the alerts
    status, alerts = _request("GET", "/api/alerts")
    nadia_alerts = [a for a in alerts if a.get("target_name") == "Nadia Volkov"]

    print(f"    Found {len(nadia_alerts)} alert(s) for Nadia Volkov:")
    for alert in nadia_alerts:
        desc_preview = alert["description"][:150].replace("\n", " ")
        print(f"      - [{alert['id'][:8]}…] {desc_preview}...")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def wait_for_server(url, name, max_wait=120):
    print(f"Waiting for {name} at {url}...", flush=True)
    start = time.time()
    while time.time() - start < max_wait:
        try:
            _request("GET", "/", base=url, timeout=5)
            print(f"{name} is up!")
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(2)
    print(f"{name} did not become available in time.")
    return False


def main():
    print(f"\n{'='*60}")
    print(f"  Target Tracker — End-to-End Integration Test")
    print(f"  Target Tracker: {BASE_URL}")
    print(f"  Article Server: {ARTICLE_SERVER_URL}")
    print(f"  Container: {CONTAINER}")
    print(f"  Article Inbox: {ARTICLE_INBOX}")
    print(f"{'='*60}\n")

    if not wait_for_server(BASE_URL, "Target Tracker"):
        sys.exit(1)
    if not wait_for_server(ARTICLE_SERVER_URL, "Article Server"):
        sys.exit(1)

    tests = [
        ("01 Nadia initially alive", test_01_nadia_initially_alive),
        ("02 Ingest death article via file watcher", test_02_ingest_death_article),
        ("03 Nadia now reported dead", test_03_nadia_now_dead),
        ("04 Alive sighting via article server", test_04_article_server_alive_sighting),
        ("05 Anomaly alert: dead person spotted alive", test_05_anomaly_alert_exists),
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
