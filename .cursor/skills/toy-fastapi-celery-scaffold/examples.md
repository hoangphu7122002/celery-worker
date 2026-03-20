# Toy Scaffold Examples (sync + webhook patterns)

Simplified patterns for sync job and webhook. Use `JobRun` and `WebhookEvent`. Full code: [celery-redis-jobs/reference.md](.cursor/skills/celery-redis-jobs/reference.md), setup: [celery-redis-jobs/setup.md](.cursor/skills/celery-redis-jobs/setup.md).

---

## worker.py

Use `settings.redis.url`, SSL branch for `rediss`, `autodiscover_tasks`, `Queue("celery")`. Full code: [reference.md](.cursor/skills/celery-redis-jobs/reference.md).

```python
from urllib.parse import urlparse
import ssl
from celery import Celery
from kombu import Queue
from config import settings

redis_ssl_options = None
if urlparse(settings.redis.url).scheme == "rediss":
    redis_ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

worker = Celery("toy", broker=settings.redis.url, backend=settings.redis.url)
worker.autodiscover_tasks(["tasks"])
worker.conf.broker_use_ssl = redis_ssl_options
worker.conf.redis_backend_use_ssl = redis_ssl_options
worker.conf.task_queues = (Queue("celery"),)
```

---

## models — JobRun and WebhookEvent

```python
from enum import Enum
from datetime import datetime
from sqlmodel import Field, SQLModel

class JobRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"

class JobRun(SQLModel, table=True):
    __tablename__ = "job_runs"
    id: int | None = Field(default=None, primary_key=True)
    status: str = Field(default=JobRunStatus.pending.value)
    created_at: datetime | None = None

class WebhookEvent(SQLModel, table=True):
    __tablename__ = "webhook_events"
    id: int | None = Field(default=None, primary_key=True)
    payload: dict = Field(default_factory=dict)
    error: str | None = None
```

---

## tasks/sync.py — Sync job

```python
from worker import worker
from tasks._async import run_async_task

@worker.task(bind=True, max_retries=0)
def sync_job(self, run_id: int) -> None:
    run_async_task(_sync_job(run_id))

async def _sync_job(run_id: int) -> None:
    async with AsyncSession(engine, ...) as session:
        run = await session.get(JobRun, run_id)
        if not run:
            return
        run.status = JobRunStatus.running.value
        await session.commit()
        # ... do work, optionally chord fan-out ...
        run.status = JobRunStatus.success.value
        await session.commit()
```

---

## tasks/webhook.py — Process webhook

```python
@worker.task(bind=True, max_retries=0)
def process_webhook(self, webhook_id: int) -> None:
    run_async_task(_process_webhook(webhook_id))

async def _process_webhook(webhook_id: int) -> None:
    async with AsyncSession(engine, ...) as session:
        event = await session.get(WebhookEvent, webhook_id)
        if event:
            # ... process payload ...
            pass
```

---

## routes/jobs.py — Sync and webhook enqueue

**Sync (create run, delay):**

```python
run = JobRun(status=JobRunStatus.pending.value)
session.add(run)
await session.commit()
await session.refresh(run)
sync_job.delay(run.id)
return run
```

**Webhook (store, delay, 202):**

```python
event = WebhookEvent(payload=await request.json())
session.add(event)
await session.commit()
await session.refresh(event)
process_webhook.delay(event.id)
return {}
```
