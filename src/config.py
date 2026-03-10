"""
config.py — Load configuration from config.yaml and .env

Usage:
    from src.config import config, get_openai_client
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Load .env file (if present) so that OPENAI_API_KEY etc. are available
# ---------------------------------------------------------------------------
load_dotenv()

# Resolve the project root relative to this file (src/ lives one level down)
_PROJECT_ROOT = Path(__file__).parent.parent


def _load_yaml() -> dict:
    """Read config.yaml from the project root."""
    config_path = _PROJECT_ROOT / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class LLMConfig:
    """Settings for the language-model backend."""

    def __init__(self, data: dict):
        self.provider: str = data.get("provider", "openai")   # "openai" | "ollama"
        self.model: str = data.get("model", "gpt-4o")
        self.base_url: str | None = data.get("base_url")       # None → use OpenAI default


class MonitorConfig:
    """Settings for the file-monitor agent."""

    def __init__(self, data: dict):
        self.watch_folder: str = data.get("watch_folder", "/tmp/news_articles")
        self.poll_interval_seconds: int = data.get("poll_interval_seconds", 30)


class DBConfig:
    """Paths for all persistent storage."""

    def __init__(self, data: dict):
        self.sqlite_path: str = data.get("sqlite_path", "data/target_tracker.db")
        self.vector_store_path: str = data.get("vector_store_path", "data/vector_store.json")
        self.document_store_path: str = data.get("document_store_path", "data/document_store.json")


class ServerConfig:
    """HTTP server settings."""

    def __init__(self, data: dict):
        self.host: str = data.get("host", "0.0.0.0")
        self.port: int = data.get("port", 5000)


class Config:
    """
    Single config object that holds all settings.

    Access like:
        config.llm.provider
        config.monitor.watch_folder
        config.db.sqlite_path
        config.server.port
    """

    def __init__(self):
        raw = _load_yaml()
        self.llm = LLMConfig(raw.get("llm", {}))
        self.monitor = MonitorConfig(raw.get("monitor", {}))
        self.db = DBConfig(raw.get("db", {}))
        self.server = ServerConfig(raw.get("server", {}))


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
config = Config()


# ---------------------------------------------------------------------------
# OpenAI client factory
# ---------------------------------------------------------------------------

def get_openai_client() -> AsyncOpenAI:
    """
    Return an AsyncOpenAI client configured for the active LLM provider.

    - For OpenAI:  uses the default base_url; OPENAI_API_KEY must be set.
    - For Ollama:  points base_url at the local Ollama server.
                   A dummy API key is passed because the client requires one,
                   but Ollama ignores it.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if config.llm.provider == "ollama":
        # Ollama exposes an OpenAI-compatible API at a local URL
        return AsyncOpenAI(
            api_key=api_key or "ollama",          # Ollama ignores the key
            base_url=config.llm.base_url or "http://localhost:11434/v1",
        )

    # Default: real OpenAI
    return AsyncOpenAI(api_key=api_key)
