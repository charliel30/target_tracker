"""
anomaly_detector.py — Anomaly Detection Agent

Triggered on every target update to check for contradictions or surprises
against existing non-temporal and temporal data.

Demonstrates direct agent-to-agent communication: this agent calls
base_target_info's lookup_target and longterm_data's get_target_temporal_data
tools directly rather than going through the orchestrator.
"""

import json
import uuid
from datetime import datetime, timezone

from agents import Agent, Runner, function_tool

from src.agents.base_target_info import lookup_target
from src.agents.longterm_data import get_target_temporal_data
from src.logging_config import get_agent_logger

log = get_agent_logger("AnomalyDetector")

# ---------------------------------------------------------------------------
# In-memory alert store
# ---------------------------------------------------------------------------

_alerts: list = []


# ---------------------------------------------------------------------------
# Agent tool
# ---------------------------------------------------------------------------

@function_tool
def check_anomaly(target_name: str, update_summary: str, existing_data: str) -> str:
    """
    Placeholder tool for the LLM to call when thinking through anomaly detection.
    Returns the inputs formatted for inspection. The real anomaly detection
    happens in the LLM's reasoning via the agent instructions.
    """
    return (
        f"TARGET: {target_name}\n"
        f"NEW UPDATE: {update_summary}\n"
        f"EXISTING DATA: {existing_data}"
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

anomaly_detection_agent = Agent(
    name="AnomalyDetector",
    instructions="""You are the Anomaly Detection Agent. You analyze target updates against existing data to find contradictions, surprises, or suspicious patterns.

When given existing target data and a new update, check for:
- A person reported deceased who is spotted alive
- A target appearing in two distant locations on the same day
- A building listed as demolished or closed that has new activity
- A vehicle reported destroyed that appears in new sightings
- Sudden dramatic changes in behavior (clean target with major criminal activity)
- Contradictions between new and existing information

If you find anomalies, describe each one clearly in a numbered list.
If no anomalies are found, respond with exactly: NO_ANOMALIES""",
    tools=[check_anomaly],
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def detect_anomalies(target_name: str, update_description: str) -> list:
    """
    Check whether a new update contradicts or conflicts with existing data
    for the given target.

    Steps:
      1. Fetch non-temporal data from base_target_info (lookup_target).
      2. Fetch temporal data from longterm_data (get_target_temporal_data).
      3. Run the anomaly_detection_agent with all context.
      4. Parse the result and create alert objects for any anomalies found.

    Returns a list of newly created alert dicts.
    """
    log.info(f"detect_anomalies: checking update for '{target_name}'")

    # --- 1. Fetch existing non-temporal data ---
    # on_invoke_tool is always async in the OpenAI Agents SDK, even for sync tools
    non_temporal_raw = await lookup_target.on_invoke_tool(
        None, json.dumps({"name": target_name})
    )
    log.debug(f"Non-temporal data for '{target_name}': {non_temporal_raw}")

    # --- 2. Fetch existing temporal data ---
    temporal_raw = await get_target_temporal_data.on_invoke_tool(
        None, json.dumps({"target_name": target_name})
    )
    log.debug(f"Temporal data for '{target_name}': {temporal_raw}")

    # --- 3. Build prompt ---
    prompt = (
        f"Target name: {target_name}\n\n"
        f"EXISTING NON-TEMPORAL DATA:\n{non_temporal_raw}\n\n"
        f"EXISTING TEMPORAL DATA:\n{temporal_raw}\n\n"
        f"NEW UPDATE:\n{update_description}\n\n"
        "Does this update conflict with or contradict existing data? "
        "Look for: person reported dead but spotted alive, same target in two "
        "distant places on same day, building demolished but has new activity, "
        "sudden dramatic changes in behavior patterns. "
        "If you find anomalies, describe each one clearly. "
        "If no anomalies, say NO_ANOMALIES."
    )

    # --- 4. Run agent ---
    log.info(f"Running anomaly detection agent for '{target_name}'")
    result = await Runner.run(anomaly_detection_agent, prompt)
    response_text = result.final_output.strip()
    log.debug(f"Agent response: {response_text}")

    # --- 5. Parse result ---
    new_alerts = []

    if response_text == "NO_ANOMALIES":
        log.info(f"No anomalies detected for '{target_name}'")
        return new_alerts

    # At least one anomaly was found — create an alert
    alert = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_name": target_name,
        "description": response_text,
    }
    _alerts.append(alert)
    new_alerts.append(alert)
    log.warning(f"Anomaly detected for '{target_name}' — alert {alert['id']} created")

    return new_alerts


# ---------------------------------------------------------------------------
# Alert management helpers
# ---------------------------------------------------------------------------

def get_alerts() -> list:
    """Return the current list of all active alerts."""
    return _alerts


def dismiss_alert(alert_id: str) -> bool:
    """
    Remove an alert by its ID.

    Returns True if the alert was found and removed, False otherwise.
    """
    global _alerts
    original_count = len(_alerts)
    _alerts = [a for a in _alerts if a["id"] != alert_id]
    removed = len(_alerts) < original_count
    if removed:
        log.info(f"Dismissed alert {alert_id}")
    else:
        log.warning(f"dismiss_alert: alert {alert_id} not found")
    return removed


def get_alert_by_id(alert_id: str) -> dict | None:
    """
    Find and return a specific alert by its ID.

    Returns the alert dict, or None if not found.
    """
    for alert in _alerts:
        if alert["id"] == alert_id:
            return alert
    return None
