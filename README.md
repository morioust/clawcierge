# Clawcierge

A secure agent registry platform that mediates access to private AI agents. External senders resolve an agent by handle, send structured requests through an enforcement pipeline, and the platform delivers validated actions to the connected agent over a persistent WebSocket channel.

## Architecture

```
Sender ──POST──▶ Platform ──pipeline──▶ WebSocket ──▶ Agent
                    │                                    │
                    │◀──────── action.result ─────────────┘
                    │
              ┌─────┴─────┐
              │  Postgres  │
              └────────────┘
```

**Enforcement pipeline** (runs on every request):
1. **Policy Engine** — evaluates declarative rules (safe expression evaluator, no `eval()`)
2. **Capability Sandbox** — validates action exists in contract, validates params via JSON Schema, enforces constraints

Both stages are fail-closed: if a stage crashes or times out, the request is rejected.

## Prerequisites

- Python 3.12+
- Docker (for PostgreSQL)
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

```bash
# 1. Clone and install
git clone git@github.com:morioust/clawcierge.git
cd clawcierge
uv sync --all-extras

# 2. Start PostgreSQL
docker compose up -d

# 3. Copy env file (defaults work out of the box with docker-compose)
cp .env.example .env

# 4. Create the test database (needed for tests only)
docker exec clawcierge-postgres-1 psql -U clawcierge -d clawcierge_dev \
  -c "CREATE DATABASE clawcierge_test;"

# 5. Run migrations
uv run alembic upgrade head

# 6. Start the server
uv run uvicorn clawcierge.main:app --reload

# 7. Verify
curl localhost:8000/health
# → {"status":"ok"}
```

## Running Tests

```bash
uv run pytest                  # all 50 tests
uv run pytest -v               # verbose
uv run pytest tests/test_pipeline.py  # specific file
```

## Usage Walkthrough

The full lifecycle: register an agent, define what it can do, connect it, then send it a request.

### 1. Register an agent

```bash
curl -s -X POST localhost:8000/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Marius Exec", "handle": "marius.exec"}' | jq
```

```json
{
  "id": "a1b2c3d4-...",
  "handle": "marius.exec",
  "api_key": "clw_agent_...",
  "display_name": "Marius Exec",
  "status": "inactive"
}
```

Save the `id` and `api_key` — the key is only shown once.

```bash
AGENT_ID="a1b2c3d4-..."
AGENT_KEY="clw_agent_..."
```

### 2. Upload capabilities

Define what actions the agent supports, with JSON Schema validation and constraints:

```bash
curl -s -X PUT localhost:8000/v1/agents/$AGENT_ID/capabilities \
  -H "Authorization: Bearer $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "capabilities": [
      {
        "action": "calendar.schedule",
        "params_schema": {
          "type": "object",
          "required": ["title", "duration_minutes"],
          "properties": {
            "title": {"type": "string"},
            "duration_minutes": {"type": "integer", "minimum": 15}
          }
        },
        "constraints": {
          "max_duration_minutes": 120
        }
      }
    ]
  }' | jq
```

Capabilities are versioned — uploading again creates a new version and deactivates the old one.

### 3. Upload policies (optional)

Define rules that reject requests based on conditions. Expressions are evaluated with a safe AST-based evaluator (no `eval()`/`exec()`):

```bash
curl -s -X PUT localhost:8000/v1/agents/$AGENT_ID/policies \
  -H "Authorization: Bearer $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [
      {
        "condition": "sender_id == \"blocked-user-id\"",
        "action": "reject",
        "reason": "Sender is blocked"
      }
    ]
  }' | jq
```

Available variables in policy expressions: `sender_id`, `action`, and `params_<field>` for each request param.

### 4. Connect the agent via WebSocket

Using the included example calendar agent:

```bash
uv run python -m agent_sdk.examples.calendar_agent \
  --url ws://localhost:8000/v1/agents/$AGENT_ID/ws \
  --token $AGENT_KEY
```

Or connect any WebSocket client. The wire protocol is JSON:

| Direction | Type | Fields |
|-----------|------|--------|
| Platform → Agent | `request.received` | `request_id`, `action`, `params`, `sender_id` |
| Platform → Agent | `request.cancel` | `request_id`, `reason` |
| Platform → Agent | `ping` | — |
| Agent → Platform | `ack` | `request_id` |
| Agent → Platform | `action.result` | `request_id`, `status`, `result`, `error` |
| Agent → Platform | `heartbeat` | — |

### 5. Resolve an agent (directory lookup)

Anyone can look up an agent by handle:

```bash
curl -s -X POST localhost:8000/v1/directory/resolve \
  -H "Content-Type: application/json" \
  -d '{"handle": "marius.exec"}' | jq
```

### 6. Send a request

Senders need an API key. For MVP, create one directly in the database, or use the agent key for testing. Requests require `Authorization: Bearer <key>`:

```bash
SENDER_KEY="clw_sender_..."  # or use agent key for testing

curl -s -X POST localhost:8000/v1/agents/marius.exec/requests \
  -H "Authorization: Bearer $SENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "calendar.schedule",
    "params": {"title": "Standup", "duration_minutes": 30}
  }' | jq
```

```json
{
  "id": "req-uuid-...",
  "status": "dispatched",
  "action_type": "calendar.schedule"
}
```

The request goes through the enforcement pipeline, then is dispatched to the agent over WebSocket. You get back `202` with a `request_id`.

### 7. Poll for the result

```bash
curl -s localhost:8000/v1/requests/$REQUEST_ID \
  -H "Authorization: Bearer $SENDER_KEY" | jq
```

```json
{
  "id": "req-uuid-...",
  "status": "completed",
  "action_type": "calendar.schedule",
  "result": {
    "event_id": "evt-...",
    "title": "Standup",
    "scheduled_time": "2026-02-11T01:00:00+00:00",
    "duration_minutes": 30,
    "status": "confirmed"
  }
}
```

### What the pipeline rejects

The enforcement pipeline blocks requests that don't match the agent's contract:

```bash
# Unknown action → 422
curl -s -X POST localhost:8000/v1/agents/marius.exec/requests \
  -H "Authorization: Bearer $SENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "email.send", "params": {}}' | jq

# Bad params (missing required field) → 422
curl -s -X POST localhost:8000/v1/agents/marius.exec/requests \
  -H "Authorization: Bearer $SENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "calendar.schedule", "params": {"title": "Sync"}}' | jq

# Constraint violation (duration > 120) → 422
curl -s -X POST localhost:8000/v1/agents/marius.exec/requests \
  -H "Authorization: Bearer $SENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "calendar.schedule", "params": {"title": "Sync", "duration_minutes": 999}}' | jq

# Agent not connected → 503
# (if the agent WebSocket is not running)
```

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | No | Health check |
| `POST` | `/v1/agents` | No | Register agent + handle, returns API key |
| `GET` | `/v1/agents/{id}` | No | Get agent details |
| `POST` | `/v1/directory/resolve` | No | Resolve handle → agent metadata |
| `PUT` | `/v1/agents/{id}/capabilities` | Agent key | Upload capability contract |
| `PUT` | `/v1/agents/{id}/policies` | Agent key | Upload policy rules |
| `POST` | `/v1/agents/{handle}/requests` | Sender key | Submit request (→ pipeline → dispatch) |
| `GET` | `/v1/requests/{id}` | Sender key | Poll for request result |
| `WS` | `/v1/agents/{id}/ws?token=` | Agent key | Agent WebSocket channel |
| `GET` | `/admin/login` | No | Admin login page |
| `POST` | `/admin/login` | No | Admin login (sets cookie) |
| `GET` | `/admin/` | Cookie | Admin dashboard (list agents) |
| `POST` | `/admin/agents/{id}/delete` | Cookie | Delete agent |
| `GET` | `/admin/logout` | No | Admin logout (clears cookie) |

Auto-generated OpenAPI docs available at `http://localhost:8000/docs` when the server is running.

## Project Structure

```
src/clawcierge/
├── main.py                    # FastAPI app, lifespan, router registration
├── config.py                  # Pydantic settings (env vars)
├── database.py                # SQLAlchemy async engine + session
├── errors.py                  # Custom exception classes
├── models/                    # SQLAlchemy ORM models
├── schemas/                   # Pydantic request/response schemas
├── services/                  # Business logic (key_manager, agent_registry, ...)
├── pipeline/                  # Enforcement pipeline (executor, policy, capability)
├── routes/                    # FastAPI route handlers
├── templates/                 # Jinja2 templates (admin UI)
└── middleware/                # Auth dependency, exception handlers

agent_sdk/                     # Lightweight Python SDK for agent authors
└── examples/calendar_agent.py # Reference agent implementation

tests/                         # 50 tests (pytest + pytest-asyncio)
```

## Configuration

All settings are loaded from environment variables (or `.env` file). See [`.env.example`](.env.example) for defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `APP_ENV` | `development` | `development` enables SQL echo |
| `LOG_LEVEL` | `info` | Logging level |
| `REQUEST_EXPIRY_SECONDS` | `300` | Time before unfinished requests expire |
| `PIPELINE_STAGE_TIMEOUT_SECONDS` | `5` | Max time per pipeline stage |
| `WS_HEARTBEAT_INTERVAL_SECONDS` | `15` | Platform ping interval |
| `WS_HEARTBEAT_TIMEOUT_SECONDS` | `60` | Max time without agent heartbeat |
| `WS_MAX_MESSAGE_SIZE` | `65536` | Max WebSocket message size (bytes) |

## Tech Stack

Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16, Pydantic v2, Jinja2, itsdangerous, simpleeval, jsonschema, structlog, uvicorn, uv, pytest, ruff.

## What's Next

Rate limiting, prompt firewall, audit logging, reputation scoring, human approval flow, real calendar integrations.
