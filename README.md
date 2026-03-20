# cursor-worker

FastAPI + Celery + Redis + PostgreSQL. Zendesk webhook/sync, OpenAI summarization, DB insert/upsert.

## System Architecture

```mermaid
flowchart TB
  subgraph Client[Client / Zendesk]
    Webhook[Webhook or job trigger]
  end

  subgraph API[FastAPI]
    Routes[HTTP routes]
  end

  subgraph Redis[Redis]
    Queue[Celery queue / broker]
  end

  subgraph Worker[Celery Worker]
    Tasks[Process webhook/sync tasks]
  end

  subgraph DB[PostgreSQL]
    Storage[Upsert payloads + sync status]
  end

  subgraph LLM[OpenAI]
    Model[LLM summarization]
  end

  subgraph Zendesk[Zendesk REST API]
    APIClient[Fetch tickets for sync]
  end

  Webhook -->|HTTP POST| Routes
  Routes -->|enqueue delay| Queue
  Queue --> Tasks

  Tasks --> Storage
  Tasks --> APIClient
  Tasks --> Model
```

## Run locally

**Terminal 1 — Redis + Postgres:**
```bash
docker compose up -d redis postgres
# Run migrations: docker run --rm --network cursor-worker_default \
#   -v $(pwd)/db/migration:/flyway/sql \
#   -e FLYWAY_URL=jdbc:postgresql://postgres:5432/cursor_worker \
#   -e FLYWAY_USER=postgres -e FLYWAY_PASSWORD=postgres \
#   flyway/flyway migrate
```

**Terminal 2 — Worker:**
```bash
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cursor_worker
celery -A worker worker -Q celery -l info
```

**Terminal 3 — FastAPI:**
```bash
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cursor_worker
uvicorn api:app --reload --port 8000
```

## Docker workers

```bash
docker compose up -d
# Scale to N worker containers:
docker compose up -d --scale worker=3
# Concurrency per container: set CELERY_CONCURRENCY in .env (default 4)
```

## Endpoints

- `POST /jobs/{job_id}` — Enqueue a job
- `POST /zendesk/webhooks` — Zendesk webhook (stores payload, enqueues process)
- `POST /zendesk/tickets/sync` — Start sync run
- `GET /zendesk/sync-requests/{id}` — Poll sync status

## Trigger a job

```bash
curl -X POST http://localhost:8000/jobs/123
# Response: {"task_id":"...", "job_id":123}
```

## Zendesk webhook (mock payload)

```bash
curl -X POST http://localhost:8000/zendesk/webhooks \
  -H "Content-Type: application/json" \
  -d '{"ticket":{"id":123,"subject":"Test","description":"Test desc","status":"new"}}'
```

## Setup

1. Copy `.env.example` to `.env` and adjust (DATABASE_URL, OPENAI_API_KEY, ZENDESK_*).
2. **LLM rate limit:** By default LLM runs for all tickets. Set `ZENDESK_LLM_LIMIT_ENABLED=true` to cap OpenAI calls per run (saves cost in dev).
3. Create virtualenv: `python -m venv .venv && source .venv/bin/activate`
4. Install: `pip install -e .`
