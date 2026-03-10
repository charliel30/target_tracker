"""
main.py — Entry point for Target Tracker

Run with:
    python -m src.main
"""

import asyncio
import json
import os
import threading
import time

from src.agents.base_target_info import load_targets
from src.agents.file_monitor import check_folder
from src.agents.longterm_data import init_stores
from src.config import config
from src.logging_config import get_agent_logger
from src.server import run_server

log = get_agent_logger("Server")

TARGETS_JSON = "data/targets.json"


# ---------------------------------------------------------------------------
# Background file-monitor loop
# ---------------------------------------------------------------------------

def _file_monitor_loop(poll_interval: int) -> None:
    """
    Poll the watch folder on a fixed interval.

    Runs in a daemon thread so it exits automatically when the main process
    stops.  Each check_folder call is async, so we use asyncio.run() to
    bridge into the event loop.
    """
    log.info(f"File monitor thread started — polling every {poll_interval}s")
    while True:
        time.sleep(poll_interval)
        try:
            asyncio.run(check_folder())
        except Exception as exc:
            log.error(f"File monitor error: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  TARGET TRACKER — Intelligence Monitoring System")
    print("=" * 60)

    # Load targets from disk into base_target_info
    log.info(f"Loading targets from {TARGETS_JSON}")
    load_targets(TARGETS_JSON)

    # Read the full targets JSON so we can pass it to the temporal stores
    with open(TARGETS_JSON, "r") as f:
        targets = json.load(f)

    # Initialise long-term data stores (async — generates embeddings)
    log.info("Initialising long-term data stores...")
    asyncio.run(init_stores(targets))

    # Create the watch folder if it doesn't exist yet
    watch_folder = config.monitor.watch_folder
    os.makedirs(watch_folder, exist_ok=True)
    log.info(f"Watch folder ready: {watch_folder}")

    # Start the file-monitor background thread
    poll_interval = config.monitor.poll_interval_seconds
    monitor_thread = threading.Thread(
        target=_file_monitor_loop,
        args=(poll_interval,),
        daemon=True,        # Dies automatically when the main process exits
        name="FileMonitorThread",
    )
    monitor_thread.start()
    log.info("File monitor thread started")

    # Start the Flask server (blocks until the process is killed)
    run_server(host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
