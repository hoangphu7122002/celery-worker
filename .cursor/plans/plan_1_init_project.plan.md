---
name: Plan 1 Init Project
overview: First plan — init a minimal FastAPI + Celery + Redis project from scratch. Phases 1–6 only. Foundation for Zendesk + OpenAI + DB later.
todos: []
isProject: false
---

# Plan 1: Init Project (FastAPI + Celery + Redis)

Minimal toy: HTTP → FastAPI → Celery (Redis) → Worker. No Postgres, no Zendesk yet. Execute each phase manually.

**Parent plan:** [fastapi_celery_project_plan_6591b345.plan.md](fastapi_celery_project_plan_6591b345.plan.md) — Phases 7+ add Zendesk, OpenAI, DB.

---

## Phases Summary


| Phase | Goal                           |
| ----- | ------------------------------ |
| 1     | Init project (pyproject, deps) |
| 2     | Config and Worker              |
| 3     | Tasks                          |
| 4     | FastAPI route                  |
| 5     | Env and run commands           |
| 6     | Local verification             |


---

## Target Directory (after Phase 6)

```
my-project/
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── config.py
├── worker.py
├── api.py
├── tasks/
│   ├── __init__.py
│   └── jobs.py
└── README.md
```

---

## Phase 1: Init Project

**Goal:** Project skeleton with dependencies.


| Step | Action                                                                                         | Reference                                                                          |
| ---- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1.1  | Create `pyproject.toml` with `uv init` or manually                                             | [toy-greenfield-scaffold](.cursor/rules/toy-greenfield-scaffold.mdc)               |
| 1.2  | Add deps: `fastapi`, `uvicorn`, `celery[redis]`, `redis`, `pydantic-settings`, `python-dotenv` | [toy-fastapi-celery-scaffold](.cursor/skills/toy-fastapi-celery-scaffold/SKILL.md) |
| 1.3  | Optional: add `ruff` for lint/format                                                           | Phase 1                                                                            |


**Check:** `uv sync` or `pip install -e .` succeeds.

---

## Phase 2: Config and Worker

**Goal:** Celery app that connects to Redis.


| Step | Action                                                                                                                    | Reference                                                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| 2.1  | Create `config.py` with `Settings` (Pydantic), `redis_url`, `@property def redis`                                         | [setup.md §2](.cursor/skills/celery-redis-jobs/setup.md)      |
| 2.2  | Create `worker.py`: Celery app, broker/backend = `settings.redis.url`, `autodiscover_tasks(["tasks"])`, `Queue("celery")` | [setup.md §3](.cursor/skills/celery-redis-jobs/setup.md)      |
| 2.3  | Add SSL branch for `rediss://`: `urlparse`, `ssl.CERT_REQUIRED`, `broker_use_ssl`                                         | [reference.md](.cursor/skills/celery-redis-jobs/reference.md) |


**Check:** `celery -A worker inspect ping` (after Redis + worker running) succeeds.

---

## Phase 3: Tasks

**Goal:** One Celery task that FastAPI can enqueue.


| Step | Action                                                                                            | Reference                                                            |
| ---- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 3.1  | Create `tasks/` directory and `tasks/__init__.py` (empty or re-exports)                           | [toy-greenfield-scaffold](.cursor/rules/toy-greenfield-scaffold.mdc) |
| 3.2  | Create `tasks/jobs.py` with `@worker.task(bind=True, max_retries=0)` (e.g. `process_job(job_id)`) | [setup.md §4](.cursor/skills/celery-redis-jobs/setup.md)             |
| 3.3  | Import `worker` from `worker` in tasks                                                            | [celery-worker-tasks](.cursor/rules/celery-worker-tasks.mdc)         |


**Check:** `process_job.delay(1)` enqueues; worker log shows task received.

---

## Phase 4: FastAPI Route

**Goal:** HTTP endpoint that enqueues a task and returns `task_id`.


| Step | Action                                                                                   | Reference                                                |
| ---- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 4.1  | Create `api.py`: FastAPI app, route `POST /jobs/{job_id}`                                | [setup.md §5](.cursor/skills/celery-redis-jobs/setup.md) |
| 4.2  | In route: `process_job.delay(job_id)`; return `{"task_id": result.id, "job_id": job_id}` | [setup.md §7](.cursor/skills/celery-redis-jobs/setup.md) |


**Check:** `curl -X POST http://localhost:8000/jobs/123` returns JSON; worker log shows task.

---

## Phase 5: Env and Run Commands

**Goal:** Reproducible local run.


| Step | Action                                                                                                                    | Reference                                                |
| ---- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 5.1  | Create `.env.example` with `REDIS_URL=redis://localhost:6379/0`                                                           | [setup.md §8](.cursor/skills/celery-redis-jobs/setup.md) |
| 5.2  | Create `docker-compose.yml` with Redis service (port 6379)                                                                | [toy-docker-local](.cursor/rules/toy-docker-local.mdc)   |
| 5.3  | Document in README: `docker compose up -d redis`; `uvicorn api:app --reload`; `celery -A worker worker -Q celery -l info` | [toy-docker-local](.cursor/rules/toy-docker-local.mdc)   |


**Check:** All three processes run; HTTP enqueue works.

---

## Phase 6: Local Verification

**Goal:** Prove the stack works locally.


| Step | Action                                                             | Reference                                                                              |
| ---- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| 6.1  | Redis: `redis-cli -u redis://localhost:6379/0 PING` → PONG         | [checklist.md](.cursor/skills/toy-celery-verify-local-azure/checklist.md)              |
| 6.2  | Worker: `celery -A worker inspect ping` (worker running)           | [toy-celery-verify-local-azure](.cursor/skills/toy-celery-verify-local-azure/SKILL.md) |
| 6.3  | HTTP enqueue: `curl -X POST .../jobs/1` → worker log shows task    | [checklist.md](.cursor/skills/toy-celery-verify-local-azure/checklist.md)              |
| 6.4  | Optional: Route test (patch `.delay`); Task test (`task.run(...)`) | [celery-testing-local-azure](.cursor/rules/celery-testing-local-azure.mdc)             |


**Milestone:** Minimal toy complete. Next: [Plan 2 / Phase 7+](fastapi_celery_project_plan_6591b345.plan.md) for Zendesk + OpenAI + DB.

---

## Key References

- **Setup code:** [.cursor/skills/celery-redis-jobs/setup.md](.cursor/skills/celery-redis-jobs/setup.md)
- **Full plan:** [fastapi_celery_project_plan_6591b345.plan.md](fastapi_celery_project_plan_6591b345.plan.md)

