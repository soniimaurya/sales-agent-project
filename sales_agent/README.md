# Persistent Sales Assistant Agent

A hosted conversational API where the agent **remembers context across sessions**, uses **real tools** to answer product questions, and **self-evaluates every response**.

## Live URL
```
https://your-app.railway.app
```
*(Replace with your Railway URL after deploy)*

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT / FRONTEND                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ POST /chat/{user_id}
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI  (main.py)                          │
│  app/api/routes.py — thin HTTP layer, validates request         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               ChatService  (services/chat_service.py)           │
│  1. Assign/reuse session_id                                     │
│  2. Save user message to DB                                     │
│  3. Call run_agent()                                            │
│  4. Call self_evaluate()                                        │
│  5. Save assistant message + eval to DB                         │
│  6. Flag if confidence < 0.5                                    │
└──────────┬───────────────────────────┬──────────────────────────┘
           │                           │
           ▼                           ▼
┌──────────────────────┐   ┌───────────────────────────────────────┐
│  Agent Loop          │   │  Memory Layer (memory/sqlite_memory)  │
│  (agents/            │   │                                       │
│   sales_agent.py)    │   │  BaseMemory (abstract interface)      │
│                      │   │  SQLiteMemory (concrete — swappable)  │
│  1. Build prompt     │   │                                       │
│  2. Call Claude API  │   │  Backed by SQLAlchemy                 │
│  3. Execute tools ◄──┼───┤  Works with SQLite (dev) or          │
│     - search_catalog │   │  Postgres (prod) via DATABASE_URL     │
│     - get_user_memory│   └───────────────────────────────────────┘
│     - flag_for_human │
│  4. Return response  │
└──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Eval Call (Claude)                      │
│  Separate prompt asking Claude to score groundedness/           │
│  relevance/confidence and flag if needed                        │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
 ChatResponse JSON  →  back to client
```

---

## Setup & Run Locally

### 1. Clone and install
```bash
git clone https://github.com/yourname/sales-agent.git
cd sales-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set your API key
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Start the server
```bash
uvicorn main:app --reload --port 8000
```

Docs available at: http://localhost:8000/docs

---

## Deploy to Railway

1. Push to GitHub
2. Create new Railway project → "Deploy from GitHub repo"
3. Add environment variable: `ANTHROPIC_API_KEY=sk-ant-...`
4. Railway auto-detects the `Procfile` and deploys

Optional Postgres: Add a Railway Postgres plugin → Railway auto-sets `DATABASE_URL`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/{user_id}` | Send a message, get response + eval |
| GET | `/chat/{user_id}/history` | Full conversation history |
| DELETE | `/chat/{user_id}/memory` | GDPR wipe |
| GET | `/catalog` | Product/pricing catalog |
| GET | `/health` | Health check |
| GET | `/chat/{user_id}/evals` | Aggregated eval scores (bonus) |

---

## Cross-Session Memory Demo (curl)

### Call 1 — User asks about Enterprise pricing
```bash
curl -X POST https://your-app.railway.app/chat/demo_user_001 \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the Enterprise plan include and how much does it cost?"}'
```

Expected: Agent calls `search_catalog` + `get_user_memory`, returns Enterprise pricing details.

### Call 2 — New session, references previous context
```bash
curl -X POST https://your-app.railway.app/chat/demo_user_001 \
  -H "Content-Type: application/json" \
  -d '{"message": "Does the plan we discussed include SSO and audit logs?"}'
```

Expected: Agent calls `get_user_memory` → retrieves session 1 context → confirms yes, SSO and audit logs are included. **No context re-sent in the request body.**

---

## Design Decisions

### Memory Design
Messages are stored in a `messages` table keyed by `user_id`. The `get_recent_context()` method pulls the last N messages across all sessions and injects them into the LLM prompt as a conversation transcript.

**Why SQLite locally?** Zero setup, single file, works on Railway free tier.  
**At scale:** Replace `DATABASE_URL` with Postgres. The `BaseMemory` abstract class means zero code changes.  
**Future:** Mem0 or a vector DB (pgvector) would enable semantic retrieval — "find the 10 most relevant past messages" rather than "find the 10 most recent."

### Eval Design
Each response is scored by a **second Claude call** with a structured JSON prompt. This is self-scoring — not an independent judge.

**Limitations:**
- Claude may be biased toward rating its own responses highly
- Scores can drift between model versions
- No ground truth to validate against

**What to replace it with in production:**
- [RAGAS](https://github.com/explodinggradients/ragas) for RAG-specific eval
- A separate smaller/cheaper model as the judge (GPT-4o-mini)
- Human-labeled golden answers for calibration

### Tool Use
Tools are defined as JSON schemas passed to `client.messages.create(tools=[...])`. Claude decides when to call them. Results are returned as `tool_result` messages — the LLM can cite them. This is fundamentally different from prompt injection because:
- Claude knows the function signature, not just a string hint
- Tool results are structured (JSON), not free text
- The tools_called list is logged for every response

---

## Running Tests
```bash
pytest tests/ -v
```

Tests cover tool logic without requiring LLM or DB.
