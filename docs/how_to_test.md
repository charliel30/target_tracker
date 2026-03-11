# How to Test Target Tracker

This guide walks through running all tests against a live Docker deployment, step by step.

## Prerequisites

- Docker and Docker Compose installed
- A valid `.env` file with your `OPENAI_API_KEY`
- Python 3.11+ on your host machine (for running test scripts)

## Step 1: Build and Start the App

The app supports two deployment modes via Docker Compose profiles:

**Ephemeral mode (recommended for testing)** — data changes stay inside the container and are discarded on restart:

```bash
docker compose --profile ephemeral up --build -d
```

**Persistent mode** — mounts the host `data/` directory so changes survive restarts:

```bash
docker compose --profile persistent up --build -d
```

The container will:
1. Install dependencies
2. Load 52 targets from `data/targets.json`
3. Generate vector embeddings (or load from cache — see below)
4. Start the Flask server on port 5000 (mapped to host port 5050)

### Embedding Cache (avoiding expensive regeneration)

The vector store generates an OpenAI embedding for every temporal data entry at startup — hundreds of API calls. To avoid paying this cost on every restart, the system caches embeddings alongside a SHA-256 hash of `targets.json`. On startup, if the hash matches, embeddings are loaded from cache instantly (zero API calls).

**First-time setup:** Run in **persistent mode** once to generate the cache on the host:

```bash
docker compose --profile persistent up --build -d
# Wait for "All stores ready" in the logs, then stop:
docker compose --profile persistent down
```

This creates `data/vector_store.json` (~10 MB) and `data/vector_store.json.hash` on your host.

**Subsequent runs:** The cache is baked into the Docker image at build time (via `COPY . .`), so both persistent and ephemeral modes start instantly:

```bash
# Either mode will use the cached embeddings:
docker compose --profile ephemeral up --build -d   # instant start
docker compose --profile persistent up --build -d  # instant start
```

**When does the cache invalidate?** Whenever `data/targets.json` changes (the hash won't match). The system automatically regenerates all embeddings and updates the cache. Incremental updates from the file monitor only embed the new entry — they don't trigger a full regeneration.

**Wait for the server to be ready.** Check the logs:

```bash
docker compose --profile ephemeral logs -f
```

Look for the line:
```
 * Running on all addresses (0.0.0.0)
```

That means the app is ready.

## Step 2: Run Functional Tests

These test the core API endpoints: index page, alerts, chat queries, distance calculations, and conversation history.

```bash
BASE_URL=http://localhost:5050 python -m tests.test_functional
```

**What it tests:**

| Test | What it does |
|------|-------------|
| Index page loads | `GET /` returns the HTML UI |
| Alerts endpoint | `GET /api/alerts` returns a JSON list |
| Chat: list targets | Asks the agent to list all target names |
| Chat: target lookup | Asks about Viktor Petrov, expects real data back |
| Chat: distance calc | Asks for distance between two targets (multi-agent) |
| Chat: conversation history | Two-turn conversation using "his" to reference a prior target |

**Expected:** All 6 tests pass. Each chat test makes a real LLM call, so expect ~2 minutes total.

## Step 3: Run Consistency Tests

These catch contradictions where different query paths return conflicting answers for the same target.

```bash
BASE_URL=http://localhost:5050 python -m tests.test_consistency
```

**What it tests:**

| Test | What it catches |
|------|----------------|
| Priors: Nadia direct vs all-data | "No priors" then revealing priors when asked for all data |
| Priors: Viktor direct vs all-data | Same pattern for Viktor Petrov |
| Priors: Chen Wei positive assertion | Known indictment must be acknowledged |
| Whereabouts: Nadia direct vs city query | "Where has she been?" vs "Who was in Paris?" |
| Whereabouts: Viktor direct vs city query | Same for Viktor in Moscow |
| Activities: Viktor direct vs all-data | Suspicious activities match across query paths |
| Activities: suspicious vs nonsuspicious | Suspicious-only query must not leak non-suspicious items |
| Cross-agent: location matches whereabouts | Current location (BaseTargetInfo) matches whereabouts (LongtermData) |
| Cross-agent: associations bidirectional | Viktor lists Nadia, Nadia lists Viktor |
| Deceased: Alexei Drozdov status | Confirmed-deceased target is reported as dead |

**Expected:** These tests are LLM-powered and may have non-deterministic failures due to LLM routing. Run multiple times to catch inconsistencies. 8–10 out of 10 passing is typical.

## Step 4: Run File Watcher Test

This tests the file-based article ingestion pipeline: dropping an article into the watch folder, waiting for the file monitor to process it, and verifying the data persists.

```bash
python -m tests.test_file_watcher
```

**What it does (step by step):**

1. Writes a news article about Nadia Volkov's death in a bus crash into the container's watch folder (`/tmp/news_articles/`)
2. Waits up to 90 seconds for the file monitor (polls every 10s) to process the file and move it to `processed/`
3. Asks the chat API: "Is Nadia Volkov alive?"
4. Asserts the response mentions she is deceased/dead/killed
5. Checks `data/targets.json` inside the container to verify a `major_event` with `event_type: "death"` and `date: "2025-11-12"` was stored

**Expected:** 1 test, passes in ~30–60 seconds (mostly waiting for the file monitor poll cycle).

**Note:** In ephemeral mode, data changes are discarded on container restart — no cleanup needed. In persistent mode, restart the container to reset:

```bash
docker compose --profile persistent down && docker compose --profile persistent up -d
```

## Step 5: Run End-to-End Test

This is the full integration test covering both ingestion paths (file watcher and article server), anomaly detection, and chat queries. It requires both the target tracker and article server containers.

```bash
python -m tests.test_end_to_end
```

**Prerequisites:** The article server container must be running (it starts automatically with any profile). Create the host inbox folder if it doesn't exist:

```bash
mkdir -p /tmp/article_inbox
```

**What it tests (in order):**

| Step | What it does |
|------|-------------|
| 01 Nadia initially alive | Ask if Nadia Volkov is dead → expect NO (clean baseline) |
| 02 Ingest death article | Drop bus crash article into container watch folder, wait for file monitor to process and store death `major_event` |
| 03 Nadia now reported dead | Ask if Nadia is dead → expect YES with death date 2025-11-12 |
| 04 Alive sighting via article server | Drop "spotted alive in Berlin" article into `/tmp/article_inbox/`, tell chatbot to fetch from article server (`http://article-server:6000/articles`) |
| 05 Anomaly alert | Check `/api/alerts` for anomaly alert (dead person spotted alive) |

**How it works:** The test exercises two ingestion paths:
- **File watcher path** (steps 2–3): Article is written directly into the container's watch folder. The file monitor polls every 10 seconds, picks it up, extracts entities via LLM, and routes updates to the data stores.
- **Article server path** (steps 4–5): Article is placed in `/tmp/article_inbox/` on the host (mounted into the article server container). The test tells the chatbot to "fetch articles from http://article-server:6000/articles" — the orchestrator calls `fetch_articles_from_url`, which GETs the articles from the article server, then processes each through the file monitor's entity extraction pipeline. The article server moves served files to `processed/`.

Anomaly detection triggers automatically during article ingestion (inside `_route_entity_updates`), not just from the orchestrator's response scanning. When the alive sighting conflicts with the recorded death, an alert is created and pushed to the alerts endpoint.

**Expected:** All 5 tests pass. Takes ~3–4 minutes total (LLM calls + file monitor poll waits).

## Running All Tests

Run all four suites in sequence using ephemeral mode (no data pollution on the host).

**Important:** If this is your first time, run in persistent mode once first to generate the embedding cache (see "Embedding Cache" above). Otherwise the first startup will take 1–2 minutes generating embeddings.

```bash
# Create article inbox folder
mkdir -p /tmp/article_inbox

# Start in ephemeral mode (with cached embeddings baked into the image)
docker compose --profile ephemeral up --build -d

# Wait for server
until curl -s http://localhost:5050 > /dev/null 2>&1; do sleep 2; done

# Run all tests
BASE_URL=http://localhost:5050 python -m tests.test_functional
BASE_URL=http://localhost:5050 python -m tests.test_consistency
python -m tests.test_file_watcher
python -m tests.test_end_to_end

# Tear down when done
docker compose --profile ephemeral down
```

**Note:** The end-to-end test must run last (or on a fresh container) because it modifies Nadia Volkov's data. In ephemeral mode, restart the containers between test runs if needed.

## Manual Testing with curl

You can also test individual queries manually:

```bash
# Ask about a target
curl -s -X POST http://localhost:5050/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Is Nadia Volkov alive?", "history": []}' | python -m json.tool

# Check alerts
curl -s http://localhost:5050/api/alerts | python -m json.tool

# Drop an article into the watch folder manually
docker exec target_tracker-target-tracker-ephemeral-1 sh -c \
  'cat > /tmp/news_articles/test_article.txt << EOF
Breaking news: Viktor Petrov was arrested in Berlin on March 5, 2026.
EOF'

# Wait 10-15 seconds for the file monitor, then query
curl -s -X POST http://localhost:5050/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Does Viktor Petrov have any major events?", "history": []}' | python -m json.tool
```

## Deployment Modes

| Mode | Command | Data volume mounted? | Use case |
|------|---------|---------------------|----------|
| **Ephemeral** | `docker compose --profile ephemeral up -d` | No | Testing, demos — changes are discarded on restart |
| **Persistent** | `docker compose --profile persistent up -d` | Yes (`./data:/app/data`) | Development, production — changes survive restarts |

Both modes mount `config.yaml` and `/tmp/news_articles` from the host.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:5050` | Server URL for functional, consistency, and end-to-end tests |
| `ARTICLE_SERVER_URL` | `http://localhost:6000` | Article server URL for end-to-end test |
| `CONTAINER` | `target_tracker-target-tracker-ephemeral-1` | Docker container name for file watcher and end-to-end tests |
| `ARTICLE_INBOX` | `/tmp/article_inbox` | Host folder mounted into article server container |

For persistent mode, override: `CONTAINER=target_tracker-target-tracker-1`

## Troubleshooting

- **Tests hang on "Waiting for server"**: Check the logs — embedding generation may still be running. If you see "Targets data changed or no cache — generating embeddings...", the cache is missing or stale. Run in persistent mode once first to generate it (see "Embedding Cache" above).
- **Consistency tests fail intermittently**: Expected. LLM routing is non-deterministic. Re-run to confirm real failures.
- **File watcher test times out**: The file monitor polls every 10 seconds. Check `docker compose --profile ephemeral logs | grep FileMonitor` to see if it's polling.
- **End-to-end test step 04 fails**: Make sure the article server container is running (`docker ps` should show `target_tracker-article-server-1`) and that `/tmp/article_inbox` exists on the host.
- **Port 5050 not available**: Edit `docker-compose.yml` to change the host port mapping, and update `BASE_URL` accordingly.
