---
name: toy-fastapi-celery-scaffold
description: Phase checklist to scaffold a minimal FastAPI + Celery + Redis project from scratch. Use when creating toy-celery-jobs/ or when the user asks for a minimal Celery app, greenfield setup, or from-scratch background jobs.
---

# Toy FastAPI Celery Scaffold (From Scratch)

Use when creating a new FastAPI + Celery + Redis project. See [celery-redis-jobs/setup.md](.cursor/skills/celery-redis-jobs/setup.md) for full worker + FastAPI setup and run commands.

## Phase 1: Init project

- `uv init` or `pyproject.toml` with deps: `fastapi`, `uvicorn`, `celery[redis]`, `redis`, `pydantic-settings`, `python-dotenv`.
- Optional: `ruff` for lint/format.

## Phase 2: Worker

- Add `worker.py`; see [reference.md](.cursor/skills/celery-redis-jobs/reference.md) or [setup.md](.cursor/skills/celery-redis-jobs/setup.md).
- Broker and backend = `settings.redis.url`; `autodiscover_tasks(["tasks"])`; single queue `celery`.

## Phase 3: Tasks

- Add `tasks/__init__.py`, `tasks/jobs.py`.
- One `@worker.task` (e.g. `add.delay(1, 2)` or `ping` returning id).
- Optional: `tasks/_async.py` with `run_async_task` if using async DB.

## Phase 4: FastAPI route

- Add `app/main.py` or `api.py`.
- Route that persists (optional) + `.delay()`; return `job_id` or pk.

## Phase 5: Env and run commands

- `.env.example` with `REDIS_URL=redis://localhost:6379/0`.
- README: `uvicorn app.main:app --reload`; `celery -A worker worker -l info`.

## Phase 6: Optional

- Beat schedule; chord fan-out toy.
- See [toy-celery-verify-local-azure](.cursor/skills/toy-celery-verify-local-azure/SKILL.md) to prove it works.

## Rules

- [toy-greenfield-scaffold](.cursor/rules/toy-greenfield-scaffold.mdc)
- [toy-docker-local](.cursor/rules/toy-docker-local.mdc)
