"""
longterm_data.py — Long-term Data Agent

Manages all temporal target intelligence data backed by three stores:
  - SQLiteStore   : structured queries (whereabouts, activities, priors)
  - VectorStore   : semantic / natural-language search via embeddings
  - DocumentStore : raw JSON source-of-truth for temporal data

The agent exposes function tools so the Orchestrator can read and write
temporal data without touching the stores directly.
"""

import json

from agents import Agent, function_tool

from src.config import config
from src.db.document_store import DocumentStore
from src.db.sqlite_store import SQLiteStore
from src.db.vector_store import VectorStore
from src.logging_config import get_agent_logger

log = get_agent_logger("LongtermData")

# ---------------------------------------------------------------------------
# Module-level store singletons (populated by init_stores)
# ---------------------------------------------------------------------------

sqlite_store: SQLiteStore = None
vector_store: VectorStore = None
document_store: DocumentStore = None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

async def init_stores(targets: dict) -> None:
    """
    Create all three store instances using paths from config and bulk-load
    the given targets dict into each.

    Must be called (and awaited) before the agent handles any requests.
    """
    global sqlite_store, vector_store, document_store

    log.info("Initialising stores...")

    sqlite_store = SQLiteStore(config.db.sqlite_path)
    vector_store = VectorStore(config.db.vector_store_path)
    document_store = DocumentStore(config.db.document_store_path)

    # SQLite and document stores are synchronous
    sqlite_store.load_targets(targets)
    document_store.load_targets(targets)

    # Vector store is async — it generates embeddings for every entry
    log.info("Generating embeddings for vector store (may take a moment)...")
    await vector_store.load_targets(targets)

    log.info("All stores ready.")


# ---------------------------------------------------------------------------
# JSON persistence helper
# ---------------------------------------------------------------------------

def save_temporal_to_json(targets_json_path: str) -> None:
    """
    Read targets.json from disk, overwrite the temporal fields for every
    target using the document store (source of truth), and write the file
    back.

    Temporal fields updated: suspicious_activities, nonsuspicious_activities,
    known_whereabouts, priors, major_events.
    """
    with open(targets_json_path, "r") as f:
        targets = json.load(f)

    for target_name in targets:
        doc_data = document_store.get_entries(target_name)
        if not doc_data:
            continue

        # Document store uses singular category keys; targets.json uses plural
        targets[target_name]["suspicious_activities"]    = doc_data.get("suspicious_activity", [])
        targets[target_name]["nonsuspicious_activities"] = doc_data.get("nonsuspicious_activity", [])
        targets[target_name]["known_whereabouts"]        = doc_data.get("whereabouts", [])
        targets[target_name]["priors"]                   = doc_data.get("prior", [])
        targets[target_name]["major_events"]             = doc_data.get("major_event", [])

    with open(targets_json_path, "w") as f:
        json.dump(targets, f, indent=2)

    log.info(f"Saved temporal data back to {targets_json_path}")


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@function_tool
def query_whereabouts(city: str, start_date: str = "", end_date: str = "") -> str:
    """
    Find targets known to have been in a given city, optionally within a date
    range. Dates should be ISO-8601 (YYYY-MM-DD).

    Example: "which targets were in New York in December 2025"
    Returns a JSON list of matches with keys: target_name, city, start_date, end_date.
    """
    log.info(f"query_whereabouts: city={city!r} start={start_date!r} end={end_date!r}")
    results = sqlite_store.query_whereabouts(
        city=city,
        start_date=start_date or None,
        end_date=end_date or None,
    )
    return json.dumps(results)


@function_tool
def query_priors(keyword: str = "") -> str:
    """
    Retrieve targets that have criminal priors, optionally filtered by a
    keyword that must appear in the prior description.

    Returns a JSON list with keys: target_name, date, description.
    """
    log.info(f"query_priors: keyword={keyword!r}")
    results = sqlite_store.query_priors(location_keyword=keyword or None)
    return json.dumps(results)


@function_tool
def query_activities(target_name: str, suspicious_only: bool = False) -> str:
    """
    Get activity records for a specific target.

    suspicious_only=True  — return only suspicious activities.
    suspicious_only=False — return both types, each tagged with a "type" field.

    Returns a JSON list with keys: target_name, timestamp, description[, type].
    """
    log.info(f"query_activities: target={target_name!r} suspicious_only={suspicious_only}")
    results = sqlite_store.query_activities(target_name, suspicious_only=suspicious_only)
    return json.dumps(results)


@function_tool
async def semantic_search(query: str) -> str:
    """
    Natural-language semantic search across all stored temporal data using
    vector embeddings.

    Example: "targets caught stealing electronics"
    Returns the top 10 most relevant results as JSON, each with keys:
    target_name, category, text, score.
    """
    log.info(f"semantic_search: query={query!r}")
    results = await vector_store.search(query, top_k=10)
    return json.dumps(results)


def do_get_target_temporal_data(target_name: str) -> str:
    """Return all temporal data for a target. Plain function — safe for direct calls."""
    log.info(f"get_target_temporal_data: target={target_name!r}")
    data = document_store.get_entries(target_name)
    return json.dumps(data)


@function_tool
def get_target_temporal_data(target_name: str) -> str:
    """
    Return all temporal data stored for a specific target (the document store
    is the canonical raw-data source).

    Returns JSON with keys: suspicious_activity, nonsuspicious_activity,
    whereabouts, prior, major_event.
    """
    return do_get_target_temporal_data(target_name)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

async def do_add_activity(target_name: str, activity_type: str, timestamp: str, description: str) -> str:
    """Add an activity. Plain async function — safe for direct calls."""
    log.info(f"add_activity: target={target_name!r} type={activity_type!r} ts={timestamp!r}")

    record = {"timestamp": timestamp, "description": description}
    sqlite_store.add_activity(target_name, activity_type, record)

    doc_category = (
        "suspicious_activity" if activity_type == "suspicious" else "nonsuspicious_activity"
    )
    document_store.add_entry(target_name, doc_category, record)

    text = (
        f"{target_name} {'suspicious activity' if activity_type == 'suspicious' else 'activity'}"
        f" on {timestamp}: {description}"
    )
    await vector_store.add_entry(target_name, doc_category, text)

    from src.config import _PROJECT_ROOT
    save_temporal_to_json(str(_PROJECT_ROOT / "data" / "targets.json"))

    return f"Activity added for {target_name} ({activity_type}) on {timestamp}."


@function_tool
async def add_activity(
    target_name: str,
    activity_type: str,
    timestamp: str,
    description: str,
) -> str:
    """
    Add a new activity for a target and persist it to all three stores.

    activity_type must be "suspicious" or "nonsuspicious".
    timestamp should be ISO-8601 (e.g. "2025-12-01").
    Also updates targets.json on disk via save_temporal_to_json.
    Returns a confirmation string.
    """
    return await do_add_activity(target_name, activity_type, timestamp, description)


async def do_add_whereabouts(target_name: str, city: str, start_date: str, end_date: str) -> str:
    """Add whereabouts. Plain async function — safe for direct calls."""
    log.info(f"add_whereabouts: target={target_name!r} city={city!r} {start_date}–{end_date}")

    record = {"city": city, "start_date": start_date, "end_date": end_date}
    sqlite_store.add_whereabouts(target_name, record)
    document_store.add_entry(target_name, "whereabouts", record)

    text = f"{target_name} was in {city} from {start_date} to {end_date}."
    await vector_store.add_entry(target_name, "whereabouts", text)

    from src.config import _PROJECT_ROOT
    save_temporal_to_json(str(_PROJECT_ROOT / "data" / "targets.json"))

    return f"Whereabouts added for {target_name}: {city} ({start_date} to {end_date})."


@function_tool
async def add_whereabouts(
    target_name: str,
    city: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Record that a target was in a given city during the specified date range
    and persist to all three stores and targets.json.

    Dates should be ISO-8601 (YYYY-MM-DD).
    Returns a confirmation string.
    """
    return await do_add_whereabouts(target_name, city, start_date, end_date)


async def do_add_prior(target_name: str, date: str, description: str) -> str:
    """Add a criminal prior. Plain async function — safe for direct calls."""
    log.info(f"add_prior: target={target_name!r} date={date!r}")

    record = {"date": date, "description": description}
    sqlite_store.add_prior(target_name, record)
    document_store.add_entry(target_name, "prior", record)

    text = f"{target_name} prior on {date}: {description}"
    await vector_store.add_entry(target_name, "prior", text)

    from src.config import _PROJECT_ROOT
    save_temporal_to_json(str(_PROJECT_ROOT / "data" / "targets.json"))

    return f"Prior added for {target_name} on {date}."


@function_tool
async def add_prior(
    target_name: str,
    date: str,
    description: str,
) -> str:
    """
    Add a criminal prior for a target and persist to all three stores and
    targets.json.

    date should be ISO-8601 (YYYY-MM-DD).
    Returns a confirmation string.
    """
    return await do_add_prior(target_name, date, description)


async def do_add_major_event(target_name: str, date: str, event_type: str, description: str) -> str:
    """Record a major event. Plain async function — safe for direct calls."""
    log.info(f"add_major_event: target={target_name!r} type={event_type!r} date={date!r}")

    record = {"date": date, "event_type": event_type, "description": description}
    sqlite_store.add_major_event(target_name, record)
    document_store.add_entry(target_name, "major_event", record)

    text = f"{target_name} major event ({event_type}) on {date}: {description}"
    await vector_store.add_entry(target_name, "major_event", text)

    from src.config import _PROJECT_ROOT
    save_temporal_to_json(str(_PROJECT_ROOT / "data" / "targets.json"))

    return f"Major event ({event_type}) recorded for {target_name} on {date}."


@function_tool
async def add_major_event(
    target_name: str,
    date: str,
    event_type: str,
    description: str,
) -> str:
    """
    Record a major event for a target and persist to all three stores and
    targets.json.

    event_type should be one of: "death", "arrest", "destruction",
    "disappearance", or another short label describing the event category.
    date should be ISO-8601 (YYYY-MM-DD).
    Returns a confirmation string.
    """
    return await do_add_major_event(target_name, date, event_type, description)


@function_tool
def query_major_events(target_name: str = "", event_type: str = "") -> str:
    """
    Query major events (deaths, arrests, destruction, disappearances, etc.).

    Both parameters are optional filters. Omit both to get all major events.
    Returns a JSON list with keys: target_name, date, event_type, description.
    """
    log.info(f"query_major_events: target={target_name!r} event_type={event_type!r}")
    results = sqlite_store.query_major_events(
        target_name=target_name or None,
        event_type=event_type or None,
    )
    return json.dumps(results)


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

longterm_data_agent = Agent(
    name="LongtermData",
    model=config.llm.model,
    instructions=(
        "You are the Long-term Data Agent for a spy target tracking system. "
        "Your responsibility is to store, retrieve, and update all temporal intelligence "
        "about tracked targets — including their activities (suspicious and non-suspicious), "
        "known whereabouts, and criminal priors. "
        "You have access to three complementary data stores: "
        "a SQLite database for structured queries, "
        "a vector store for natural-language semantic search, "
        "and a document store as the raw source of truth. "
        "When asked to search or filter intelligence data, choose the most appropriate tool: "
        "use query_whereabouts for location-based queries, query_priors for criminal history, "
        "query_activities for a specific target's activity log, "
        "query_major_events for deaths/arrests/destruction/disappearances, "
        "and semantic_search for broad natural-language queries. "
        "When adding new intelligence, always use the add_* tools so all stores stay in sync. "
        "IMPORTANT: When asked about a target's status (alive, dead, missing, etc.) or for ALL "
        "data on a target, always check major_events — these record critical status changes "
        "like deaths, arrests, and disappearances."
    ),
    tools=[
        query_whereabouts,
        query_priors,
        query_activities,
        query_major_events,
        semantic_search,
        get_target_temporal_data,
        add_activity,
        add_whereabouts,
        add_prior,
        add_major_event,
    ],
)
