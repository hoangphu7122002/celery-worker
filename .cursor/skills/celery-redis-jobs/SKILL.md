---
name: celery-redis-jobs
description: Reference patterns for Celery worker, tasks, sync/webhook, chord/chain, Postgres, OpenAI, Flyway, and Azure. Use when building FastAPI+Celery+Redis+Postgres from scratch or explaining full-flow deployment.
---

# Celery Redis Jobs

Use when building a FastAPI + Celery + Redis project from scratch. All code is self-contained in this skill.

## Full Zendesk flow

See [zendesk-full-flow.md](.cursor/skills/celery-redis-jobs/zendesk-full-flow.md) for complete flow: webhook, sync, OpenAI summarization, database (SQLModel/AsyncSession), Redis LLM limiter. Full code: [reference.md](.cursor/skills/celery-redis-jobs/reference.md) (Postgres, Redis, ZendeskService, run_async_task).

## Worker + FastAPI setup

See [setup.md](.cursor/skills/celery-redis-jobs/setup.md) for complete setup: config, worker, FastAPI app, run commands (Redis, worker, API), Postgres (optional), OpenAI (optional), and how to trigger tasks from HTTP.

## Flyway migrations

See [flyway-migrations.md](.cursor/skills/celery-redis-jobs/flyway-migrations.md) for SQL migrations with Flyway instead of Alembic: folder layout, CLI usage, Azure migration job.

## Azure deployment

See [azure-deploy-full](.cursor/rules/azure-deploy-full.mdc): PostgreSQL Flexible Server, Redis Cache, Container Apps (API, Worker, Migration Job), Key Vault, build→migrate→deploy flow.

## Code samples

See [reference.md](.cursor/skills/celery-redis-jobs/reference.md) for copy-paste snippets: worker, tasks, routes, run_async_task, models.

## Code style

See [ai-code-style-reference](.cursor/rules/ai-code-style-reference.mdc): minimal change, OOP, env vars (single underscore, Pydantic Settings), `run_async_task` pattern.

## Worker setup

- One Celery app in `worker.py`; broker and backend = `settings.redis.url`.
- `autodiscover_tasks(["tasks"])`; single queue `celery`; worker command `-Q celery`.

## Task definition

- `@worker.task(bind=True, max_retries=0)`; import `worker` from `worker`.
- Thin sync wrapper + `async def _...` implementation + `run_async_task` for async DB.

## Recipe A: Sync job

1. Create run row (`SyncRequest`), status `pending`, commit.
2. `sync_zendesk_tickets.delay(run.id)`.
3. Pipeline: load run, set `running`, fetch ids via `_sync_zendesk_events`, then `chord(group(chain(sync_ticket.s(id), process_ticket.s()) for id in ids), update_sync_request.s(run_id))`.
4. Poll `GET /zendesk/sync-requests/{id}` for status (not Celery result backend).

## Recipe B: Webhook

1. Persist `ZendeskWebhook` payload, commit.
2. `process_zendesk_webhook.delay(event.id)`.
3. Task re-checks `settings.zendesk_webhook_enabled`; gate in route too.

## Recipe C: Scheduled daily

- Beat entry in `worker.conf.beat_schedule`; task creates run row inside, then `sync_job.delay(run.id)`.

## Local vs Azure testing

- **Local:** Patch `.delay` in route tests; `task.run(...)` in task tests; `ENVIRONMENT=test`, `.env.test`.
- **Azure:** Same `REDIS_URL` (rediss) for API and worker; smoke `POST /zendesk/tickets/sync` + poll; App Insights for logs; do not rely on Celery results for job status.

## Rules

- [celery-worker-tasks](.cursor/rules/celery-worker-tasks.mdc)
- [postgres-setup](.cursor/rules/postgres-setup.mdc)
- [openai-setup](.cursor/rules/openai-setup.mdc)
- [flyway-migrations](.cursor/rules/flyway-migrations.mdc)
- [azure-deploy-full](.cursor/rules/azure-deploy-full.mdc)
- [celery-redis-infra](.cursor/rules/celery-redis-infra.mdc)
- [celery-testing-local-azure](.cursor/rules/celery-testing-local-azure.mdc)
