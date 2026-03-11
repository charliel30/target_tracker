"""
orchestrator.py — Orchestrator Agent

Central router for all user chat requests. Uses handoffs to delegate to
specialized sub-agents, and owns a few multi-agent coordination tools directly.
"""

import json
import re
import urllib.request
import urllib.error

from agents import Agent, Runner, function_tool

from src.config import config
from src.logging_config import get_agent_logger
from src.agents.base_target_info import base_target_info_agent, lookup_target, do_lookup_target
from src.agents.calculator import calculator_agent, calculate_age, calculate_distance, do_calculate_age, do_calculate_distance
from src.agents.longterm_data import longterm_data_agent
from src.agents.file_monitor import file_monitor_agent, process_article_text

log = get_agent_logger("Orchestrator")


# ---------------------------------------------------------------------------
# Multi-agent coordination tools (orchestrator calls sub-agent tools directly)
# ---------------------------------------------------------------------------

@function_tool
async def calculate_distance_between_targets(target_name_1: str, target_name_2: str) -> str:
    """
    Calculate the distance in km between two tracked targets.

    Fetches each target's current_location (expected as [lat, lon]) from
    BaseTargetInfo, then delegates the haversine calculation to Calculator.
    """
    log.info(f"calculate_distance_between_targets: '{target_name_1}' <-> '{target_name_2}'")

    # Fetch non-temporal data for both targets
    raw1 = do_lookup_target(target_name_1)
    raw2 = do_lookup_target(target_name_2)

    if raw1 == "not found":
        return f"Target '{target_name_1}' not found."
    if raw2 == "not found":
        return f"Target '{target_name_2}' not found."

    try:
        data1 = json.loads(raw1)
        data2 = json.loads(raw2)
    except json.JSONDecodeError as exc:
        return f"Error parsing target data: {exc}"

    loc1 = data1.get("current_location")
    loc2 = data2.get("current_location")

    if not loc1:
        return f"No location data available for '{target_name_1}'."
    if not loc2:
        return f"No location data available for '{target_name_2}'."

    # current_location is a dict {"lat": ..., "lon": ...}
    result = do_calculate_distance(loc1["lat"], loc1["lon"], loc2["lat"], loc2["lon"])

    log.info(f"Distance between '{target_name_1}' and '{target_name_2}': {result}")
    return f"Distance between {target_name_1} and {target_name_2}: {result}"


@function_tool
async def calculate_target_age(target_name: str) -> str:
    """
    Calculate the current age of a tracked target.

    Fetches the target's birthday from BaseTargetInfo, then delegates the
    age calculation to Calculator.
    """
    log.info(f"calculate_target_age: '{target_name}'")

    raw = do_lookup_target(target_name)

    if raw == "not found":
        return f"Target '{target_name}' not found."

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"Error parsing target data: {exc}"

    birthday = data.get("birthday")
    if not birthday:
        return f"No birthday on record for '{target_name}'."

    result = do_calculate_age(birthday)
    log.info(f"Age of '{target_name}': {result}")
    return f"{target_name} is {result}."


@function_tool
async def fetch_articles_from_url(url: str) -> str:
    """
    Fetch articles from a REST URL (expects a JSON array of article objects),
    then process each article's text through the FileMonitor agent.

    Returns a summary of how many articles were fetched and how many target
    updates were made.
    """
    log.info(f"fetch_articles_from_url: {url}")

    # HTTP GET — stdlib only, no third-party deps
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        log.error(f"Failed to fetch articles from {url}: {exc}")
        return f"Error fetching articles: {exc}"

    try:
        articles = json.loads(body)
        if not isinstance(articles, list):
            return "Expected a JSON array of articles from the URL."
    except json.JSONDecodeError as exc:
        return f"Could not parse JSON response: {exc}"

    log.info(f"Fetched {len(articles)} article(s) from {url}")

    total_updates = 0
    for i, article in enumerate(articles):
        # Support both {"text": "..."} objects and plain strings
        if isinstance(article, dict):
            text = article.get("text") or article.get("content") or article.get("body") or ""
        else:
            text = str(article)

        if not text.strip():
            log.debug(f"Article {i+1} is empty — skipping")
            continue

        updates = await process_article_text(text)
        total_updates += len(updates)
        log.info(f"Article {i+1}: {len(updates)} update(s) applied")

    return (
        f"Processed {len(articles)} article(s) from {url}. "
        f"Total target updates applied: {total_updates}."
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

orchestrator_agent = Agent(
    name="Orchestrator",
    model=config.llm.model,
    instructions="""You are the Orchestrator Agent for the Target Tracker spy network intelligence system. You route user requests to the appropriate specialized agents.

Available agents (via handoff):
- BaseTargetInfo: Knows non-temporal target data (names, types, locations, associations, characteristics). Hand off to this agent for target lookups, listing targets, and updating non-temporal information.
- Calculator: Performs math operations. For age calculations and distance calculations, use the calculate_target_age and calculate_distance_between_targets tools instead of handing off directly.
- LongtermData: Knows temporal target data (activities, whereabouts, priors, major events). Hand off for queries about when/where targets were seen, criminal history, suspicious activities, and major events (deaths, arrests, destruction, disappearances). IMPORTANT: When asked about a target's status (alive/dead/missing), always check with LongtermData for major events.
- FileMonitor: Processes articles to extract target information. Use fetch_articles_from_url tool for URL-based fetching.

For UPDATE requests:
1. First identify the target (use BaseTargetInfo for fuzzy matching if needed)
2. Confirm the match with the user before applying updates
3. After updates, the system will automatically check for anomalies

For QUERIES spanning multiple agents (e.g., "tell me everything about Target X"):
- Gather information from both BaseTargetInfo and LongtermData
- Combine into a comprehensive response

Always be concise and professional in your responses. You are helping intelligence analysts track targets.""",
    tools=[calculate_distance_between_targets, calculate_target_age, fetch_articles_from_url],
    handoffs=[base_target_info_agent, calculator_agent, longterm_data_agent, file_monitor_agent],
)


# ---------------------------------------------------------------------------
# Main entry point — called by the Flask server
# ---------------------------------------------------------------------------

async def handle_user_message(message: str, conversation_history: list) -> dict:
    """
    Process a user chat message through the orchestrator pipeline.

    Args:
        message:              The latest user message text.
        conversation_history: Full prior conversation as list of
                              {"role": "user"|"assistant", "content": "..."} dicts.

    Returns:
        {"response": str, "new_alerts": list}
    """
    log.info(f"handle_user_message: {message[:80]!r}{'...' if len(message) > 80 else ''}")

    # --- Build full prompt from history + new message ---
    # The SDK's Runner.run accepts a plain string; we prepend history as context
    history_text = ""
    for turn in conversation_history:
        role = turn.get("role", "user").capitalize()
        content = turn.get("content", "")
        history_text += f"{role}: {content}\n"

    # Check if message references an alert ID — inject alert context if so
    from src.agents.anomaly_detector import get_alert_by_id
    alert_context = ""
    # Look for UUID-like patterns in the message
    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    for alert_id in re.findall(uuid_pattern, message, re.IGNORECASE):
        alert = get_alert_by_id(alert_id)
        if alert:
            alert_context = (
                f"\n[ALERT CONTEXT — ID {alert_id}]\n"
                f"Target: {alert['target_name']}\n"
                f"Description: {alert['description']}\n"
                f"Timestamp: {alert['timestamp']}\n"
            )
            log.info(f"Injecting context for alert {alert_id}")
            break

    full_prompt = (
        f"{history_text}"
        f"User: {message}"
        f"{alert_context}"
    ).strip()

    # --- Run orchestrator ---
    log.info("Running orchestrator agent")
    result = await Runner.run(orchestrator_agent, full_prompt)
    response_text = result.final_output or ""
    log.info(f"Orchestrator response: {response_text[:120]!r}{'...' if len(response_text) > 120 else ''}")

    # --- Check for anomalies triggered by any updates in this turn ---
    # We scan the response for update indicators and run anomaly detection
    new_alerts = []
    update_keywords = ["updated", "added", "recorded", "stored", "modified"]
    response_lower = response_text.lower()

    if any(kw in response_lower for kw in update_keywords):
        log.info("Update indicators found in response — running anomaly checks")
        from src.agents.anomaly_detector import detect_anomalies

        # Extract target names mentioned in the response using a simple heuristic:
        # look for quoted names or names after "for" / "target"
        mentioned = set()
        for m in re.finditer(r"['\"]([^'\"]+)['\"]", response_text):
            mentioned.add(m.group(1))
        for m in re.finditer(r"(?:target|for)\s+([A-Z][a-zA-Z\s\-']+?)(?:\s*[,.\n]|$)", response_text):
            mentioned.add(m.group(1).strip())

        for target_name in mentioned:
            if len(target_name) < 3:
                continue
            try:
                alerts = await detect_anomalies(target_name, f"Update from user session: {message}")
                new_alerts.extend(alerts)
            except Exception as exc:
                log.warning(f"Anomaly detection failed for '{target_name}': {exc}")

    log.info(f"handle_user_message complete — {len(new_alerts)} new alert(s)")
    return {"response": response_text, "new_alerts": new_alerts}
