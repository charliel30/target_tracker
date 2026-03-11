"""
base_target_info.py — Base Target Info Agent

Manages non-temporal target data (type, current_location, birthday,
associations, identifying_characteristics) in an in-memory dict loaded
from targets.json.  Temporal fields (activities, whereabouts, priors)
are left to the Long-term Data Agent.
"""

import json
from agents import Agent, function_tool

from src.config import config, get_openai_client
from src.logging_config import get_agent_logger

log = get_agent_logger("BaseTargetInfo")

# Default path to the targets file — override by calling load_targets() directly
DATA_PATH = "data/targets.json"

# The non-temporal fields this agent owns
NON_TEMPORAL_FIELDS = {
    "type",
    "current_location",
    "birthday",
    "associations",
    "identifying_characteristics",
}

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_target_data: dict = {}


# ---------------------------------------------------------------------------
# Load / save helpers
# ---------------------------------------------------------------------------

def load_targets(targets_json_path: str = DATA_PATH) -> None:
    """
    Read targets.json and populate _target_data with only the non-temporal
    fields for each target.  Called once at startup.
    """
    global _target_data
    with open(targets_json_path, "r") as f:
        raw = json.load(f)

    _target_data = {
        name: {k: v for k, v in fields.items() if k in NON_TEMPORAL_FIELDS}
        for name, fields in raw.items()
    }
    log.info(f"Loaded {len(_target_data)} targets from {targets_json_path}")


def save_targets(targets_json_path: str = DATA_PATH) -> None:
    """
    Merge in-memory non-temporal changes back into the full targets.json and
    write to disk.  We always read first so we never lose temporal fields.
    """
    with open(targets_json_path, "r") as f:
        full_data = json.load(f)

    for name, fields in _target_data.items():
        if name not in full_data:
            # New target added entirely in-memory — write it as-is
            full_data[name] = fields
        else:
            # Merge only the fields this agent owns
            full_data[name].update(fields)

    with open(targets_json_path, "w") as f:
        json.dump(full_data, f, indent=2)

    log.info(f"Saved target data to {targets_json_path}")


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------

def do_lookup_target(name: str) -> str:
    """Return JSON of a target's non-temporal data, or 'not found'.
    Plain function — safe to call directly from other agents."""
    if name not in _target_data:
        log.debug(f"lookup_target: '{name}' not found")
        return "not found"
    log.debug(f"lookup_target: returning data for '{name}'")
    return json.dumps(_target_data[name])


@function_tool
def lookup_target(name: str) -> str:
    """Return JSON of a target's non-temporal data, or 'not found'."""
    return do_lookup_target(name)


@function_tool
def list_all_targets() -> str:
    """Return a JSON list of all known target names."""
    keys = list(_target_data.keys())
    log.debug(f"list_all_targets: {len(keys)} targets")
    return json.dumps(keys)


@function_tool
def list_targets_by_type(target_type: str) -> str:
    """Return a JSON list of target names whose type matches target_type."""
    matches = [
        name for name, fields in _target_data.items()
        if fields.get("type", "").lower() == target_type.lower()
    ]
    log.debug(f"list_targets_by_type('{target_type}'): {len(matches)} matches")
    return json.dumps(matches)


def do_update_target_field(target_name: str, field: str, value: str) -> str:
    """Update a non-temporal field. Plain function — safe for direct calls."""
    if target_name not in _target_data:
        log.warning(f"update_target_field: target '{target_name}' not found")
        return f"Target '{target_name}' not found."

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    # For list fields, append new items rather than replacing the entire list.
    existing = _target_data[target_name].get(field)
    if isinstance(existing, list) and isinstance(parsed_value, list):
        for item in parsed_value:
            # For associations (list of objects with target_name), dedup by target_name
            if field == "associations" and isinstance(item, dict) and "target_name" in item:
                existing_names = {
                    e.get("target_name") for e in existing if isinstance(e, dict)
                }
                if item["target_name"] not in existing_names:
                    existing.append(item)
            elif item not in existing:
                existing.append(item)
        log.info(f"Appended to '{target_name}'.{field} ({len(parsed_value)} item(s))")
    else:
        _target_data[target_name][field] = parsed_value
        log.info(f"Updated '{target_name}'.{field}")

    save_targets()
    return f"Updated '{target_name}'.{field} successfully."


@function_tool
def update_target_field(target_name: str, field: str, value: str) -> str:
    """
    Update a single non-temporal field for a target and persist to disk.
    value must be a JSON-encoded string (e.g. '"London"' or '[1,2,3]').
    Returns a confirmation message.
    """
    return do_update_target_field(target_name, field, value)


@function_tool
def get_associations(target_name: str) -> str:
    """Return the associations list for a target as a JSON string."""
    if target_name not in _target_data:
        log.debug(f"get_associations: '{target_name}' not found")
        return "not found"
    associations = _target_data[target_name].get("associations", [])
    log.debug(f"get_associations: '{target_name}' has {len(associations)} associations")
    return json.dumps(associations)


# ---------------------------------------------------------------------------
# Fuzzy lookup (not a tool — called directly by other agents/orchestrator)
# ---------------------------------------------------------------------------

async def fuzzy_lookup(query: str) -> str | None:
    """
    Ask the LLM to find the best matching target key for a loose query.
    Returns the matched key string, or None if no confident match is found.

    This is intentionally NOT a @function_tool — it's a utility for Python
    callers that want semantic name matching without an exact key.
    """
    all_keys = list(_target_data.keys())
    if not all_keys:
        return None

    prompt = (
        f"You are a name-matching assistant. Given the query '{query}', "
        f"identify the single best matching name from this list:\n"
        f"{json.dumps(all_keys)}\n\n"
        f"Reply with ONLY the exact name from the list, or 'none' if there is "
        f"no reasonable match."
    )

    client = get_openai_client()
    response = await client.chat.completions.create(
        model=config.llm.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    result = response.choices[0].message.content.strip()
    log.debug(f"fuzzy_lookup('{query}') -> '{result}'")

    if result.lower() == "none" or result not in _target_data:
        return None
    return result


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

base_target_info_agent = Agent(
    name="BaseTargetInfo",
    model=config.llm.model,
    instructions=(
        "You are the Base Target Info Agent for a spy network tracking system. "
        "You manage non-temporal information about targets: their type (person, "
        "vehicle, building), current location, birthday, known associations, and "
        "identifying characteristics. "
        "Use your tools to look up, list, and update target records. "
        "When asked to find a target by an approximate or partial name, use "
        "list_all_targets to retrieve the full list and pick the closest match. "
        "ASSOCIATIONS: Each association is an object with 'target_name' and 'description'. "
        "When asked about a target's associations, list the associated target names first. "
        "Only provide association descriptions when the user specifically asks for details "
        "about how targets are associated or connected. "
        "Always confirm updates to the user. Be concise and factual."
    ),
    tools=[
        lookup_target,
        list_all_targets,
        list_targets_by_type,
        update_target_field,
        get_associations,
    ],
    # model is intentionally omitted — set at runtime via Runner
)
