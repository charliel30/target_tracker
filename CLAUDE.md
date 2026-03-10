# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Target Tracker is a **teaching application** for software developers learning to build agentic AI systems using the **OpenAI Agents SDK**. It simulates a spy network that tracks people, buildings, and vehicles through a multi-agent architecture with a simple web chat UI.

**Primary goal: readability and learnability.** Keep code simple, well-logged, and easy to follow. Avoid unnecessary abstractions, heavy frameworks, or clever patterns that obscure what the agents are doing.

## Quick Start

```bash
# Without Docker
cp .env.example .env          # Add your OPENAI_API_KEY (or configure Ollama in config.yaml)
pip install -r requirements.txt
python -m src.main             # Starts Flask server on http://localhost:5000

# With Docker
cp .env.example .env
docker-compose up --build
```

## Run a Single Component

```bash
python -m src.main                      # Full app (Flask + all agents)
python data/generate_targets.py         # Generate synthetic targets to fill data/targets.json
```

## Architecture Summary

Six agents orchestrated through a central orchestrator, all using the OpenAI Agents SDK:

- **Orchestrator Agent** — Routes user chat requests to the right agent(s). All user queries go through here.
- **Base Target Info Agent** — Manages non-temporal target data (name, location, associations, identifying characteristics). Holds data in a Python dict loaded from `data/targets.json`. Uses LLM for fuzzy name matching.
- **Calculator Agent** — Math operations: age from birthdate, haversine distance between target locations.
- **Long-term Data Agent** — Manages temporal target data (activities, whereabouts, priors). Backed by 3 DB types: SQLite, vector store (RAG), and JSON document store.
- **File Monitor Agent** — Watches a configurable folder (default `/tmp/news_articles`) for new files. Extracts entities, matches against known targets, triggers updates. Moves processed files to a `processed/` subfolder.
- **Anomaly Detection Agent** — Triggered on any target update. Checks if new data conflicts with existing data (e.g., dead person spotted alive). Pushes alerts to the UI.

An **MCP server** (side module in `src/mcp/`) lets the file monitor agent fetch articles from a REST URL.

## Key Design Decisions

- **LLM provider is config-driven** (`config.yaml`): switch between OpenAI API and Ollama (OpenAI-compatible endpoint) without code changes. All agents share the same LLM.
- **All data loads from `data/targets.json` at startup**, agents modify in-memory state, and changes are written back to the JSON file so they persist across restarts.
- **Agent-to-agent communication**: the orchestrator handles most routing, but some agents call others directly (e.g., anomaly agent calls base-target-info and long-term-data agents directly). Both patterns are shown for teaching purposes.
- **Fuzzy target lookup uses the LLM**, not string matching libraries — demonstrates that LLMs handle semantic matching well.
- **Each agent logs in a distinct color** to make orchestration flow visible in the terminal.

## Config Files

- **`config.yaml`** — LLM provider/model, monitor folder path, DB settings, logging preferences.
- **`.env`** — API keys only (OPENAI_API_KEY). Never committed.

## UI

Simple HTML + vanilla JS served by Flask. No frontend frameworks. Chat window (75% width) + alerts sidebar (25% width, top half). The browser stores conversation context and sends the full history with each request.

## Code Style

- Python 3.11+
- Keep files short and focused — one agent per file
- Prefer stdlib over third-party when possible
- Comments should explain *why*, not *what*
- Logging is a first-class feature: every agent action should be logged with its colored prefix
