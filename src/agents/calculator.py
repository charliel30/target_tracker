"""
calculator.py — Calculator Agent

Provides age and geographic distance calculations via function tools.
"""

import math
from datetime import date, datetime

from agents import Agent, function_tool

from src.config import config
from src.logging_config import get_agent_logger

log = get_agent_logger("Calculator")


def do_calculate_age(birthdate: str) -> str:
    """Calculate age from ISO date. Plain function — safe for direct calls."""
    born = datetime.strptime(birthdate, "%Y-%m-%d").date()
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    log.info("Age calculation: %s → %d years old", birthdate, age)
    return f"{age} years old (born {birthdate})"


def do_calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Haversine distance in km. Plain function — safe for direct calls."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    distance = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    log.info(
        "Distance calculation: (%.4f, %.4f) → (%.4f, %.4f) = %.1f km",
        lat1, lon1, lat2, lon2, distance,
    )
    return f"{distance:.1f} km"


@function_tool
def calculate_age(birthdate: str) -> str:
    """Calculate a person's age from an ISO date string (e.g. '1985-03-15')."""
    return do_calculate_age(birthdate)


@function_tool
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Calculate the great-circle distance in km between two coordinates using the haversine formula."""
    return do_calculate_distance(lat1, lon1, lat2, lon2)


calculator_agent = Agent(
    name="Calculator",
    model=config.llm.model,
    instructions=(
        "You are the Calculator Agent. You perform mathematical calculations for the target tracking system. "
        "You can calculate a person's age from their birthdate, and calculate the distance between two geographic "
        "coordinates using the haversine formula. Always use the appropriate tool for calculations - never estimate."
    ),
    tools=[calculate_age, calculate_distance],
)
