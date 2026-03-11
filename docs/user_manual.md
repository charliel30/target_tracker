# Target Tracker — User Manual

## What Is This?

Target Tracker is an intelligence management tool. You interact with it through a web chat interface to query, update, and monitor information about tracked targets — people, buildings, and vehicles.

Behind the scenes, a team of AI agents collaborates to fulfill your requests.

## Getting Started

### 1. Configure

Edit `config.yaml` to set your LLM provider:

**Using OpenAI API:**
```yaml
llm:
  provider: "openai"
  model: "gpt-5.2"
```
Add your API key to `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

**Using Ollama (local):**
```yaml
llm:
  provider: "ollama"
  model: "llama3"
  base_url: "http://localhost:11434/v1"
```
Make sure Ollama is running: `ollama serve`

### 2. Start the App

```bash
# Install dependencies
pip install -r requirements.txt

# Start
python -m src.main
```

Open your browser to `http://localhost:5000`.

### 3. Start with Docker (alternative)

```bash
docker-compose up --build
```

## The Interface

```
┌──────────────────────────────────┬──────────────────┐
│                                  │   ALERTS          │
│          CHAT WINDOW             │                   │
│                                  │  ⚠ Alert text [x]│
│  You: your message here          │  ⚠ Alert text [x]│
│  Agent: response here            │                   │
│                                  │                   │
│                                  │                   │
│                                  │                   │
│  [Type your message...] [Send]   │                   │
└──────────────────────────────────┴──────────────────┘
```

- **Chat Window (left, 75%):** Type questions or commands. The conversation history is preserved in your browser.
- **Alerts Sidebar (right top, 25%):** Anomaly alerts appear here automatically. Click the `[x]` to dismiss. Alerts are ordered by date, newest first.

## What You Can Do

### Query Targets

Ask about any target by name. Exact spelling isn't required — the system uses AI to find the best match.

```
You: Tell me about Jessica Alba
You: What do we know about jessica albo?
You: Give me info on the black SUV
You: What targets are associated with the Embassy building?
```

### List Targets

```
You: List all vehicle targets
You: How many person targets do we have?
You: Show me all targets associated with Viktor Petrov
```

### Query Temporal Data

Ask about activities, whereabouts, and criminal history.

```
You: Which targets were in New York City in December 2025?
You: How many of our targets have priors in Colorado?
You: Give me targets that were caught stealing electronics in Texas
You: What suspicious activity has been reported for Target X?
You: Where was Maria Santos last seen?
```

### Calculate

Ask for computed values. The system fetches the needed data and does the math.

```
You: How old is Viktor Petrov?
You: How far apart are Jessica Alba and the Embassy building?
You: What's the distance between the black SUV and the warehouse on 5th?
```

### Update Targets

Add new information about a target. The system will confirm the target match before applying the update.

```
You: Update Jessica Alba's location to 40.7128, -74.0060
You: Add a prior for Viktor Petrov: arrested for espionage on 2025-06-15
You: Add suspicious activity for the black SUV: spotted near restricted military base on 2025-11-20
You: Add known whereabouts for Maria Santos: Tokyo, from 2025-09-01 to 2025-09-15
```

**Confirmation flow:**
```
You: Add a prior for Viktor Petrov: arrested for espionage on 2025-06-15
Agent: I found target "Viktor Petrov" (person). I'm about to add this prior:
       "Arrested for espionage" on 2025-06-15.
       Is this correct? (yes/no)
You: yes
Agent: Updated. Viktor Petrov now has 4 priors on record.
```

### Fetch Articles from a URL

Ask the system to fetch intelligence articles from a remote source.

```
You: Fetch articles from http://localhost:8080/articles
You: Check for new articles at http://localhost:8080/feed
```

The system will:
1. Fetch the article list from the URL (via MCP server)
2. Scan each article for mentions of known targets
3. Automatically update target records with relevant information
4. Report what it found and what was updated
5. Flag any anomalies as alerts

### Reference Alerts

When alerts appear in the sidebar, you can ask about them in the chat.

```
You: Tell me more about that alert for Viktor Petrov
You: What's the context on alert #2?
You: Why was there an anomaly for the black SUV?
```

## File-Based Article Ingestion

Place text files (articles, reports, intelligence briefs) into the monitored folder (default: `/tmp/news_articles`). The system will:

1. Automatically detect new files
2. Read and extract mentions of people, buildings, and vehicles
3. Match extracted entities against known targets
4. Update target records with relevant information
5. Move processed files to `/tmp/news_articles/processed/`
6. Trigger anomaly detection on any updates

You can change the monitored folder in `config.yaml`:
```yaml
monitor:
  watch_folder: "/path/to/your/folder"
```

## Alerts

Alerts are generated automatically when the anomaly detection agent spots something unusual in a target update. Examples:

- A person who was reported deceased is spotted alive
- A vehicle appears in two distant locations on the same day
- A building listed as demolished has new activity reported
- A person with no criminal history suddenly has a major prior added

Alerts appear in the sidebar with:
- A timestamp of when the anomaly was detected
- A description of what was flagged
- The target it relates to

Click `[x]` to dismiss an alert. Dismissed alerts are removed from the UI.

## Tips

- **Natural language works.** You don't need exact commands — just describe what you want in plain English.
- **Misspellings are okay.** The system uses AI to match target names, so close-enough works.
- **Check the terminal.** Colored logs show which agents are working, what they're doing, and how they communicate. This is the best way to understand the multi-agent architecture.
- **Data persists.** All changes are saved back to `data/targets.json`, so your updates survive restarts.

## Running Tests

Functional tests verify the API endpoints against a running server:

```bash
# With the server running (locally or via Docker)
python -m tests.test_functional

# Or point at a different host
BASE_URL=http://host:port python -m tests.test_functional
```

Tests cover: UI loading, alerts API, target listing, target lookup, distance calculations, and conversation history.
