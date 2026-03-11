# How to Test Target Tracker

This guide walks through running all tests against a live Docker deployment, step by step.

## Prerequisites

- Docker and Docker Compose installed
- A valid `.env` file with your `OPENAI_API_KEY`
- Python 3.11+ on your host machine (for running test scripts)

## Step 1: Build and Start the App

```bash
# From the project root
docker compose up --build -d
```

The container will:
1. Install dependencies
2. Load 52 targets from `data/targets.json`
3. Generate vector embeddings (takes 1–2 minutes on first start)
4. Start the Flask server on port 5000 (mapped to host port 5050)

**Wait for the server to be ready.** Check the logs:

```bash
docker compose logs -f
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

This tests the full article ingestion pipeline: dropping an article into the watch folder, waiting for the file monitor to process it, and verifying the data persists.

```bash
python -m tests.test_file_watcher
```

**What it does (step by step):**

1. Writes a news article about Nadia Volkov's death in a bus crash into the container's watch folder (`/tmp/news_articles/`)
2. Waits up to 90 seconds for the file monitor (polls every 30s) to process the file and move it to `processed/`
3. Asks the chat API: "Is Nadia Volkov alive?"
4. Asserts the response mentions she is deceased/dead/killed
5. Checks `data/targets.json` inside the container to verify a `major_event` with `event_type: "death"` and `date: "2025-11-12"` was stored

**Expected:** 1 test, passes in ~60 seconds (mostly waiting for the file monitor poll cycle).

**Note:** This test modifies target data. To reset, restart the container:

```bash
docker compose down && docker compose up -d
```

## Running All Tests

Run all three suites in sequence:

```bash
# Make sure Docker is running
docker compose up -d

# Wait for server
until curl -s http://localhost:5050 > /dev/null 2>&1; do sleep 2; done

# Run all tests
BASE_URL=http://localhost:5050 python -m tests.test_functional
BASE_URL=http://localhost:5050 python -m tests.test_consistency
python -m tests.test_file_watcher
```

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
docker exec target_tracker-target-tracker-1 sh -c \
  'cat > /tmp/news_articles/test_article.txt << EOF
Breaking news: Viktor Petrov was arrested in Berlin on March 5, 2026.
EOF'

# Wait 30-40 seconds for the file monitor, then query
curl -s -X POST http://localhost:5050/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Does Viktor Petrov have any major events?", "history": []}' | python -m json.tool
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:5050` | Server URL for functional and consistency tests |
| `CONTAINER` | `target_tracker-target-tracker-1` | Docker container name for file watcher test |

## Troubleshooting

- **Tests hang on "Waiting for server"**: Check `docker compose logs` — the embedding generation may still be running.
- **Consistency tests fail intermittently**: Expected. LLM routing is non-deterministic. Re-run to confirm real failures.
- **File watcher test times out**: The file monitor polls every 30 seconds. Check `docker compose logs | grep FileMonitor` to see if it's polling.
- **Port 5050 not available**: Edit `docker-compose.yml` to change the host port mapping, and update `BASE_URL` accordingly.
