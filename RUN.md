# Run and Test All Services

## Option A: All in Docker

```bash
# 1. Start everything (redis, postgres, worker)
docker compose up -d

# 2. Run migrations
docker run --rm --network cursor-worker_default \
  -v $(pwd)/db/migration:/flyway/sql \
  -e FLYWAY_URL=jdbc:postgresql://postgres:5432/cursor_worker \
  -e FLYWAY_USER=postgres \
  -e FLYWAY_PASSWORD=postgres \
  flyway/flyway migrate

# 3. Scale workers (optional): run N worker containers
docker compose up -d --scale worker=3

# 4. Set concurrency per container (in .env or docker-compose)
# CELERY_CONCURRENCY=4  # default: 4 worker processes per container
```

## Option B: Host-run API + Worker, Docker infra only

## 1. Start infrastructure (Redis + Postgres)

```bash
docker compose up -d redis postgres
```

## 2. Run Flyway migrations (if using docker Postgres)

```bash
docker run --rm --network cursor-worker_default \
  -v $(pwd)/db/migration:/flyway/sql \
  -e FLYWAY_URL=jdbc:postgresql://postgres:5432/cursor_worker \
  -e FLYWAY_USER=postgres \
  -e FLYWAY_PASSWORD=postgres \
  flyway/flyway migrate
```

## 3. Start Worker (Terminal 2)

**Docker:**
```bash
docker compose up -d worker
# Or with custom concurrency: CELERY_CONCURRENCY=8 docker compose up -d worker
# Or scale to 3 containers: docker compose up -d --scale worker=3
```

**Host:**
```bash
source .venv/bin/activate
celery -A worker worker -Q celery -l info
```

## 4. Start FastAPI (Terminal 3)

```bash
source .venv/bin/activate
uvicorn api:app --reload --port 8000
```

Or load `.env` automatically:

```bash
source .venv/bin/activate
set -a && source .env && set +a
uvicorn api:app --reload --port 8000
```

---

## PostgreSQL connection string (remote DB client)

Use in DBeaver, pgAdmin, DataGrip, TablePlus, etc.
**Docker Postgres (cursor_worker):**

```
postgresql://postgres:postgres@localhost:5432/cursor_worker
```
---

## Test commands

```bash
# 1. Redis
docker exec cursor-worker-redis-1 redis-cli PING
# → PONG

# 2. Worker
celery -A worker inspect ping
# → pong

# 3. Job
curl -X POST http://localhost:8000/jobs/123

# 4. Zendesk webhook (mock)
curl -X POST http://localhost:8000/zendesk/webhooks \
  -H "Content-Type: application/json" \
  -d '{"ticket":{"id":999,"subject":"Test","description":"Test desc","status":"new"}}'

# 5. Zendesk sync
curl -X POST http://localhost:8000/zendesk/tickets/sync -H "Content-Type: application/json" -d '{}'

# 6. Poll sync status
curl http://localhost:8000/zendesk/sync-requests/1
```
