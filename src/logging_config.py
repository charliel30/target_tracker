"""
logging_config.py — Colored console logging for each agent.

Usage:
    from src.logging_config import get_agent_logger

    log = get_agent_logger("Orchestrator")
    log.info("Pipeline started")
"""

import logging
import sys

# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------
RESET = "\033[0m"

COLORS = {
    "Orchestrator":    "\033[96m",   # Cyan
    "BaseTargetInfo":  "\033[92m",   # Green
    "Calculator":      "\033[93m",   # Yellow
    "LongtermData":    "\033[95m",   # Magenta
    "FileMonitor":     "\033[94m",   # Blue
    "AnomalyDetector": "\033[91m",   # Red
    "MCP":             "\033[97m",   # White
}

# Fall-back color for any agent not in the table above
DEFAULT_COLOR = "\033[37m"  # Light gray


# ---------------------------------------------------------------------------
# Custom formatter that injects color around the agent-name prefix
# ---------------------------------------------------------------------------

class ColoredAgentFormatter(logging.Formatter):
    """
    Wraps the logger name with its assigned ANSI color so each agent's
    output is visually distinct in the terminal.
    """

    def __init__(self, agent_name: str, color: str):
        self.agent_name = agent_name
        self.color = color
        # Format:  [AgentName] LEVEL  message
        fmt = f"{color}[{agent_name}]{RESET} %(levelname)-8s %(message)s"
        super().__init__(fmt=fmt)


# ---------------------------------------------------------------------------
# Public factory function
# ---------------------------------------------------------------------------

def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Return a Logger for the given agent, already configured with a colored
    handler.  Calling this multiple times with the same name is safe — Python's
    logging module returns the same Logger instance each time.

    Args:
        agent_name: One of the known agent names (see COLORS dict) or any
                    arbitrary string.  Unknown names get a gray prefix.

    Returns:
        A standard logging.Logger ready to use.
    """
    logger = logging.getLogger(agent_name)

    # Avoid adding duplicate handlers if this function is called more than once
    if logger.handlers:
        return logger

    color = COLORS.get(agent_name, DEFAULT_COLOR)

    # Stream handler — write to stdout so Docker logs / terminals show output
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredAgentFormatter(agent_name, color))

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Prevent messages from bubbling up to the root logger (avoids duplicates)
    logger.propagate = False

    return logger
