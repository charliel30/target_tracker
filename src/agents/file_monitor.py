"""
file_monitor.py — File Monitor Agent

Watches a folder for new article files, uses the LLM to extract entity
mentions (people, buildings, vehicles), fuzzy-matches them against known
targets, and routes updates to the appropriate agent:
  - Non-temporal info  →  base_target_info (update_target_field)
  - Temporal info      →  longterm_data (add_activity / add_whereabouts / add_prior)

Processed files are moved to a `processed/` subfolder inside the watch folder.

This module demonstrates direct agent-to-agent communication: the FileMonitor
Agent calls base_target_info and longterm_data functions without going through
the Orchestrator.
"""

import json
import os
import shutil

from agents import Agent, Runner, function_tool

from src.config import config
from src.logging_config import get_agent_logger

# Lazy imports to avoid circular dependencies at module load time
# (base_target_info and longterm_data are imported inside functions that
#  need them, which is safe because all agents are initialised before
#  check_folder is ever called.)

log = get_agent_logger("FileMonitor")


# ---------------------------------------------------------------------------
# Tool (used by the agent's own reasoning to structure its output)
# ---------------------------------------------------------------------------

@function_tool
def process_article(content: str) -> str:
    """
    Extract entity mentions from the given article text.

    Returns a JSON array where each element describes one entity found in
    the article.  Each element has the shape:
      {
        "name": "...",
        "type": "person" | "building" | "vehicle",
        "temporal": [
          {"category": "suspicious_activity"|"nonsuspicious_activity"|"whereabouts"|"prior",
           "description": "...",
           "date": "YYYY-MM-DD or empty string"}
        ],
        "non_temporal": {
          "identifying_characteristics": [...],
          ... any other non-temporal field ...
        }
      }

    The caller (the agent's own reasoning loop) is responsible for returning
    the populated JSON array as its final answer.
    """
    # This tool exists so the agent can call it as a structured output helper.
    # The real extraction happens via the agent's reasoning; we just pass the
    # content through as context.
    return f"Article content received ({len(content)} chars). Extract all entity mentions now."


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

file_monitor_agent = Agent(
    name="FileMonitor",
    model=config.llm.model,
    instructions="""You are the File Monitor Agent. When given article text, you extract mentions of people, buildings, and vehicles. For each entity found, provide:
- The entity name as mentioned in the article
- The entity type (person, building, or vehicle)
- Any temporal information (activities, whereabouts, incidents, major events)
- Any non-temporal information (physical descriptions, NEW associations to ADD)

IMPORTANT: For temporal data, use the correct category:
- "suspicious_activity" — covert meetings, unauthorized access, espionage
- "nonsuspicious_activity" — normal daily activities
- "whereabouts" — must include a real city name, start_date, and end_date
- "prior" — criminal charges, arrests, law enforcement encounters
- "major_event" — deaths, destruction, disappearances, major arrests. Must include "event_type" (e.g. "death", "destruction", "arrest", "disappearance")

For non_temporal fields: only include NEW characteristics or associations to ADD to existing records. Do not repeat or summarize existing data.

Return your findings as a JSON array. Example:
[{"name": "John Smith", "type": "person", "temporal": [{"category": "major_event", "event_type": "death", "description": "killed in car accident on Highway 101", "date": "2025-12-01"}], "non_temporal": {}}]""",
    tools=[process_article],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_entities(llm_output: str) -> list:
    """
    Extract the JSON array from the agent's final text output.
    Returns an empty list if parsing fails.
    """
    # The agent may wrap the JSON in markdown code fences — strip them
    text = llm_output.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence line and any closing fence
        inner = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        # Agent may have returned {"entities": [...]}
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return val
    except json.JSONDecodeError as exc:
        log.warning(f"Could not parse entity JSON from LLM output: {exc}")

    return []


async def _route_entity_updates(entity: dict, matched_target: str) -> list[dict]:
    """
    Given an extracted entity dict and the fuzzy-matched canonical target name,
    call the appropriate update functions, trigger anomaly detection, and return
    a list of update records.
    """
    # Import here to avoid circular imports at module load time
    from src.agents.base_target_info import do_update_target_field, NON_TEMPORAL_FIELDS
    from src.agents.longterm_data import (
        do_add_activity, do_add_whereabouts, do_add_prior, do_add_major_event,
    )
    from src.agents.anomaly_detector import detect_anomalies

    updates = []

    # --- Non-temporal updates ---
    non_temporal = entity.get("non_temporal", {})
    for field, value in non_temporal.items():
        if field not in NON_TEMPORAL_FIELDS:
            continue
        do_update_target_field(matched_target, field, json.dumps(value))
        log.info(f"Non-temporal update for '{matched_target}': {field} = {value!r}")
        updates.append({
            "target": matched_target,
            "update_type": "non_temporal",
            "field": field,
            "value": value,
        })

    # --- Temporal updates ---
    for temporal_item in entity.get("temporal", []):
        category = temporal_item.get("category", "")
        description = temporal_item.get("description", "")
        date = temporal_item.get("date", "")

        if not description:
            continue

        if category in ("suspicious_activity", "nonsuspicious_activity"):
            activity_type = "suspicious" if category == "suspicious_activity" else "nonsuspicious"
            await do_add_activity(matched_target, activity_type, date, description)
            log.info(f"Activity added for '{matched_target}' ({activity_type}) on {date!r}")
            updates.append({
                "target": matched_target,
                "update_type": "activity",
                "activity_type": activity_type,
                "date": date,
                "description": description,
            })

        elif category == "whereabouts":
            city = temporal_item.get("city", description.split()[0] if description else "unknown")
            end_date = temporal_item.get("end_date", date)
            await do_add_whereabouts(matched_target, city, date, end_date)
            log.info(f"Whereabouts added for '{matched_target}': {city} on {date!r}")
            updates.append({
                "target": matched_target,
                "update_type": "whereabouts",
                "city": city,
                "date": date,
            })

        elif category == "prior":
            await do_add_prior(matched_target, date, description)
            log.info(f"Prior added for '{matched_target}' on {date!r}")
            updates.append({
                "target": matched_target,
                "update_type": "prior",
                "date": date,
                "description": description,
            })

        elif category == "major_event":
            event_type = temporal_item.get("event_type", "unknown")
            await do_add_major_event(matched_target, date, event_type, description)
            log.info(f"Major event ({event_type}) added for '{matched_target}' on {date!r}")
            updates.append({
                "target": matched_target,
                "update_type": "major_event",
                "event_type": event_type,
                "date": date,
                "description": description,
            })

        else:
            log.debug(f"Unknown temporal category '{category}' for '{matched_target}' — skipped")

    # --- Anomaly detection ---
    if updates:
        update_summary = "; ".join(
            f"{u['update_type']}: {u.get('description', u.get('field', ''))}"
            for u in updates
        )
        try:
            alerts = await detect_anomalies(matched_target, update_summary)
            if alerts:
                log.warning(f"Anomaly detected for '{matched_target}': {len(alerts)} alert(s)")
        except Exception as exc:
            log.error(f"Anomaly detection failed for '{matched_target}': {exc}")

    return updates


async def _extract_and_route(text: str) -> list[dict]:
    """
    Core logic shared by check_folder and process_article_text.

    1. Sends the article text to file_monitor_agent via Runner.run to extract entities.
    2. Fuzzy-matches each entity name against known targets.
    3. Routes updates to the appropriate agent modules.

    Returns a list of update dicts describing every change that was made.
    """
    from src.agents.base_target_info import fuzzy_lookup

    # Ask the agent to extract entities
    result = await Runner.run(file_monitor_agent, f"Extract all entity mentions from this article:\n\n{text}")
    llm_output = result.final_output or ""

    entities = _parse_entities(llm_output)
    log.info(f"Extracted {len(entities)} entity mention(s) from article")

    all_updates: list[dict] = []

    for entity in entities:
        name = entity.get("name", "").strip()
        if not name:
            continue

        matched = await fuzzy_lookup(name)
        if matched is None:
            log.debug(f"No known target matched '{name}' — skipping")
            continue

        log.info(f"Matched entity '{name}' -> known target '{matched}'")
        updates = await _route_entity_updates(entity, matched)
        all_updates.extend(updates)

    return all_updates


# ---------------------------------------------------------------------------
# Module-level functions called by the system
# ---------------------------------------------------------------------------

async def check_folder() -> list[dict]:
    """
    Check the configured watch folder for new article files.

    For each file found:
      - Read its content
      - Extract entity mentions via the LLM
      - Update base_target_info / longterm_data for matched targets
      - Move the file to a `processed/` subfolder

    Returns a list of all update dicts made across all files.  The caller
    (main.py background loop) forwards this list to the Anomaly Detector.
    """
    watch_folder = config.monitor.watch_folder

    if not os.path.isdir(watch_folder):
        log.debug(f"Watch folder does not exist yet: {watch_folder}")
        return []

    processed_dir = os.path.join(watch_folder, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    # Collect plain files only (skip the processed/ subdir and dotfiles)
    try:
        entries = os.listdir(watch_folder)
    except OSError as exc:
        log.error(f"Cannot list watch folder '{watch_folder}': {exc}")
        return []

    files = [
        e for e in entries
        if os.path.isfile(os.path.join(watch_folder, e)) and not e.startswith(".")
    ]

    if not files:
        log.debug(f"No new files in '{watch_folder}'")
        return []

    all_updates: list[dict] = []

    for filename in files:
        filepath = os.path.join(watch_folder, filename)
        log.info(f"Processing file: {filename}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            log.error(f"Failed to read '{filename}': {exc}")
            continue

        if not content.strip():
            log.warning(f"File '{filename}' is empty — skipping")
            shutil.move(filepath, os.path.join(processed_dir, filename))
            continue

        try:
            updates = await _extract_and_route(content)
            all_updates.extend(updates)
            log.info(f"File '{filename}' produced {len(updates)} update(s)")
        except Exception as exc:
            log.error(f"Error processing '{filename}': {exc}")
            # Still move the file so we don't reprocess it on every poll
        finally:
            dest = os.path.join(processed_dir, filename)
            try:
                shutil.move(filepath, dest)
                log.debug(f"Moved '{filename}' -> processed/")
            except OSError as exc:
                log.error(f"Could not move '{filename}' to processed/: {exc}")

    return all_updates


async def process_article_text(text: str) -> list[dict]:
    """
    Process a single article string without any file I/O.

    Used by the MCP article fetcher path when content arrives as a string
    rather than as a file on disk.

    Returns a list of update dicts describing every change that was made.
    """
    log.info(f"Processing article text ({len(text)} chars)")

    if not text.strip():
        log.warning("process_article_text called with empty text — nothing to do")
        return []

    updates = await _extract_and_route(text)
    log.info(f"Article text produced {len(updates)} update(s)")
    return updates
