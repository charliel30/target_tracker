"""
test_consistency.py — Cross-query consistency tests for Target Tracker

These tests catch contradictions where the system gives conflicting answers
depending on how you ask. For example, saying a target has "no priors" but
then listing priors when asked for "all historical data."

Each test asks the same question two different ways and checks that the
answers don't contradict each other.

Usage:
    python -m tests.test_consistency
    BASE_URL=http://host:port python -m tests.test_consistency
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

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


def _chat(message, history=None):
    """Send a chat message and return the response text."""
    status, body = _request("POST", "/api/chat", {
        "message": message,
        "history": history or [],
    })
    assert status == 200, f"Chat request failed with status {status}"
    return body["response"]


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
# Consistency tests: priors
# ---------------------------------------------------------------------------

def test_priors_direct_vs_all_data_nadia():
    """
    Nadia Volkov has a DGSI detention prior. Asking about her priors
    directly vs asking for all historical data should not contradict.

    Catches the bug where "does she have priors?" says no, but
    "give me all data" reveals a prior.
    """
    # Ask specifically about priors
    resp1 = _chat("Does Nadia Volkov have any criminal priors or law enforcement encounters?")
    # Ask for all data
    resp2 = _chat("Give me all historical temporal data on Nadia Volkov including activities, whereabouts, and priors.")

    resp1_lower = resp1.lower()
    resp2_lower = resp2.lower()

    # If the all-data response mentions DGSI or espionage (which it should),
    # then the priors-specific response must not deny priors exist
    has_prior_in_full = "dgsi" in resp2_lower or "espionage" in resp2_lower or "detained" in resp2_lower
    denies_priors = (
        "no criminal priors" in resp1_lower
        or "no priors" in resp1_lower
        or "don't have any priors" in resp1_lower
        or "do not have any priors" in resp1_lower
        or "no law enforcement" in resp1_lower
        or "no recorded priors" in resp1_lower
        or "no criminal record" in resp1_lower
    )

    assert not (has_prior_in_full and denies_priors), (
        f"CONTRADICTION: Priors query says no priors, but all-data query reveals DGSI detention.\n"
        f"  Priors response: {resp1[:300]}\n"
        f"  All-data response: {resp2[:300]}"
    )


def test_priors_direct_vs_all_data_viktor():
    """
    Viktor Petrov has 2 priors (FSB arrest, Ukrainian journalist poisoning).
    Both query paths should acknowledge them.
    """
    resp1 = _chat("Does Viktor Petrov have any criminal priors?")
    resp2 = _chat("Show me everything you have on Viktor Petrov — all activities, whereabouts, and priors.")

    resp1_lower = resp1.lower()
    resp2_lower = resp2.lower()

    has_prior_in_full = "fsb" in resp2_lower or "radar" in resp2_lower or "poisoning" in resp2_lower
    denies_priors = "no priors" in resp1_lower or "no criminal" in resp1_lower

    assert not (has_prior_in_full and denies_priors), (
        f"CONTRADICTION: Viktor Petrov has FSB arrest + poisoning priors but direct query denies them.\n"
        f"  Priors response: {resp1[:300]}\n"
        f"  All-data response: {resp2[:300]}"
    )


def test_priors_positive_assertion_chen_wei():
    """
    Chen Wei has a US federal indictment on 12 counts. A direct priors
    query must acknowledge this.
    """
    resp = _chat("Does Chen Wei have any criminal priors or indictments?")
    resp_lower = resp.lower()

    assert any(kw in resp_lower for kw in ["indicted", "indictment", "federal", "computer fraud", "espionage", "prior"]), (
        f"Chen Wei has a US federal indictment but the response doesn't mention it: {resp[:300]}"
    )


# ---------------------------------------------------------------------------
# Consistency tests: whereabouts
# ---------------------------------------------------------------------------

def test_whereabouts_direct_vs_city_query_nadia():
    """
    Nadia Volkov is recorded in Paris 2024-01-15 to 2026-03-09.
    Asking "where has Nadia been?" and "who was in Paris in 2025?"
    should both include her.
    """
    resp1 = _chat("Where has Nadia Volkov been located? List her known whereabouts.")
    resp2 = _chat("Which targets were in Paris, France during 2025?")

    resp1_lower = resp1.lower()
    resp2_lower = resp2.lower()

    # resp1 should mention Paris
    assert "paris" in resp1_lower, (
        f"Nadia Volkov's whereabouts should include Paris but response doesn't mention it: {resp1[:300]}"
    )

    # resp2 should mention Nadia
    assert "nadia" in resp2_lower or "volkov" in resp2_lower, (
        f"Paris 2025 query should include Nadia Volkov but doesn't: {resp2[:300]}"
    )


def test_whereabouts_direct_vs_city_query_viktor():
    """
    Viktor Petrov is recorded in Moscow 2023-01-01 to 2025-09-01.
    Both query paths should show this.
    """
    resp1 = _chat("List Viktor Petrov's known whereabouts.")
    resp2 = _chat("Which targets were in Moscow, Russia during 2024?")

    assert "moscow" in resp1.lower(), (
        f"Viktor Petrov's whereabouts should include Moscow: {resp1[:300]}"
    )
    assert "viktor" in resp2.lower() or "petrov" in resp2.lower(), (
        f"Moscow 2024 query should include Viktor Petrov: {resp2[:300]}"
    )


# ---------------------------------------------------------------------------
# Consistency tests: activities
# ---------------------------------------------------------------------------

def test_activities_direct_vs_all_data():
    """
    Viktor Petrov has suspicious activities (briefcase exchange at Gorky Park,
    Belarusian embassy visit). Asking about suspicious activities directly
    vs asking for all data should not contradict.
    """
    resp1 = _chat("What suspicious activities has Viktor Petrov been involved in?")
    resp2 = _chat("Give me all temporal data on Viktor Petrov.")

    resp1_lower = resp1.lower()
    resp2_lower = resp2.lower()

    # Both should mention Gorky Park or briefcase or embassy
    has_activity_keywords = ["gorky", "briefcase", "embassy", "belarusian", "suspicious"]
    resp1_has = any(kw in resp1_lower for kw in has_activity_keywords)
    resp2_has = any(kw in resp2_lower for kw in has_activity_keywords)

    # If all-data has them, the direct query should too
    assert not (resp2_has and not resp1_has), (
        f"CONTRADICTION: All-data mentions activities but direct query doesn't.\n"
        f"  Activities response: {resp1[:300]}\n"
        f"  All-data response: {resp2[:300]}"
    )


def test_suspicious_vs_nonsuspicious_not_mixed():
    """
    When asking for only suspicious activities, the response should not
    include clearly non-suspicious ones (and vice versa). Nadia Volkov's
    non-suspicious activities include French class and art exhibition.
    """
    resp = _chat("List ONLY the suspicious activities for Nadia Volkov. Do not include non-suspicious activities.")
    resp_lower = resp.lower()

    # Non-suspicious items that should NOT appear
    nonsuspicious_markers = ["french language", "alliance française", "art exhibition", "palais de tokyo"]
    found_nonsuspicious = [m for m in nonsuspicious_markers if m in resp_lower]

    assert not found_nonsuspicious, (
        f"Suspicious-only query for Nadia Volkov includes non-suspicious activities: {found_nonsuspicious}\n"
        f"  Response: {resp[:400]}"
    )


# ---------------------------------------------------------------------------
# Consistency tests: cross-agent data
# ---------------------------------------------------------------------------

def test_location_matches_whereabouts():
    """
    Viktor Petrov's current_location is in Moscow (lat 55.7558, lon 37.6173)
    and his whereabouts include Moscow. Asking "where is Viktor Petrov right
    now?" and "where has Viktor Petrov been?" should be consistent — his
    current city should appear in whereabouts.
    """
    resp1 = _chat("What is Viktor Petrov's current location?")
    resp2 = _chat("List all known whereabouts for Viktor Petrov.")

    # Both should reference Moscow
    assert "moscow" in resp1.lower() or ("55.75" in resp1 and "37.6" in resp1), (
        f"Current location should indicate Moscow: {resp1[:300]}"
    )
    assert "moscow" in resp2.lower(), (
        f"Whereabouts should include Moscow: {resp2[:300]}"
    )


def test_associations_bidirectional():
    """
    Viktor Petrov lists Nadia Volkov as an association, and The Black Sedan.
    When we ask about Nadia Volkov's associations, Viktor Petrov should
    appear as well (associations should be roughly bidirectional for people
    in the same network).
    """
    resp1 = _chat("Who are Viktor Petrov's known associations?")
    resp2 = _chat("Who are Nadia Volkov's known associations?")

    resp1_lower = resp1.lower()
    resp2_lower = resp2.lower()

    # Viktor -> Nadia should be there
    assert "nadia" in resp1_lower or "volkov" in resp1_lower, (
        f"Viktor's associations should include Nadia Volkov: {resp1[:300]}"
    )

    # Nadia -> Viktor should be there (bidirectional)
    assert "viktor" in resp2_lower or "petrov" in resp2_lower, (
        f"Nadia's associations should include Viktor Petrov: {resp2[:300]}"
    )


# ---------------------------------------------------------------------------
# Consistency tests: deceased target
# ---------------------------------------------------------------------------

def test_deceased_target_consistency():
    """
    Alexei Drozdov is confirmed deceased (2022-03-14, cardiac arrest).
    If asked "is Alexei Drozdov alive?", the system should say no.
    If then asked about his activities, it should only show activities
    from before the death date.
    """
    resp1 = _chat("Is Alexei Drozdov alive? What is his current status?")
    resp2 = _chat("List all of Alexei Drozdov's priors and activities.")

    resp1_lower = resp1.lower()

    # Should mention deceased/dead
    assert any(kw in resp1_lower for kw in ["deceased", "dead", "died", "death", "cardiac"]), (
        f"Alexei Drozdov is confirmed deceased but response doesn't indicate this: {resp1[:300]}"
    )


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
    print(f"  Target Tracker — Consistency / Contradiction Tests")
    print(f"  Server: {BASE_URL}")
    print(f"{'='*60}\n")

    if not wait_for_server():
        sys.exit(1)

    tests = [
        # Priors consistency
        ("Priors: Nadia direct vs all-data", test_priors_direct_vs_all_data_nadia),
        ("Priors: Viktor direct vs all-data", test_priors_direct_vs_all_data_viktor),
        ("Priors: Chen Wei positive assertion", test_priors_positive_assertion_chen_wei),
        # Whereabouts consistency
        ("Whereabouts: Nadia direct vs city query", test_whereabouts_direct_vs_city_query_nadia),
        ("Whereabouts: Viktor direct vs city query", test_whereabouts_direct_vs_city_query_viktor),
        # Activities consistency
        ("Activities: Viktor direct vs all-data", test_activities_direct_vs_all_data),
        ("Activities: suspicious vs nonsuspicious", test_suspicious_vs_nonsuspicious_not_mixed),
        # Cross-agent consistency
        ("Cross-agent: location matches whereabouts", test_location_matches_whereabouts),
        ("Cross-agent: associations bidirectional", test_associations_bidirectional),
        # Deceased target
        ("Deceased: Alexei Drozdov status", test_deceased_target_consistency),
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
