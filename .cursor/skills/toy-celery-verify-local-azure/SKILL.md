---
name: toy-celery-verify-local-azure
description: Verification matrix for Celery-backed toy projects: local Redis PING, worker startup, HTTP enqueue, pytest mocks, Azure staging smoke. Use when debugging "it doesn't run", "deployed but no worker", or CI smoke.
---

# Toy Celery Verify (Local and Azure)

Use when debugging "it doesn't run", "deployed but no worker", or CI smoke.

## Local matrix

1. **Redis:** `redis-cli -u redis://localhost:6379/0 PING` → `PONG`.
2. **Worker startup:** `celery -A worker worker -l info` → log "connected to redis".
3. **Inspect:** `celery -A worker inspect ping` (with worker running).
4. **HTTP enqueue:** `POST /jobs` (or equivalent) → worker log shows task received.

## Test matrix

- **Route:** Patch `task.delay`; assert `call_args[0][0]` for enqueued id.
- **Task:** `task.run(...)` with mocked I/O; no broker required.

## Azure matrix

1. Both API and worker use same `REDIS_URL` (rediss).
2. TLS URL; worker has `broker_use_ssl` when scheme is `rediss`.
3. Worker scale > 0; revision running.
4. Log stream: enqueue from deployed API → worker picks up task.
5. Log Analytics query hints for "task received" troubleshooting.

## Rules

- [celery-testing-local-azure](.cursor/rules/celery-testing-local-azure.mdc)
- [toy-azure-minimal](.cursor/rules/toy-azure-minimal.mdc)
