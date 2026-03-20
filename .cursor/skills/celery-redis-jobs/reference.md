# Code Reference

Copy-paste snippets for FastAPI + Celery + Redis + Postgres. Full code samples below.

## Zendesk + OpenAI + DB

See [zendesk-full-flow.md](.cursor/skills/celery-redis-jobs/zendesk-full-flow.md) for the complete flow: webhook/sync routes, Celery tasks, ZendeskService (DB + Zendesk API), OpenAI `summarize_ticket_to_motion`, Redis LLM limiter.

---

## config.py — Settings (Redis, Postgres, OpenAI)

```python
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(".env", override=False) or load_dotenv(".env.dev", override=False)
if environment := os.getenv("ENVIRONMENT", "").lower():
    load_dotenv(f".env.{environment}", override=True)

class DatabaseSettings(BaseModel):
    url: str

class RedisSettings(BaseModel):
    url: str

class OpenAISettings(BaseModel):
    api_key: str | None = None
    base_url: str | None = None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str
    redis_url: str
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    environment: str | None = None

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(url=self.database_url)

    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(url=self.redis_url)

    @property
    def openai(self) -> OpenAISettings:
        return OpenAISettings(api_key=self.openai_api_key, base_url=self.openai_base_url)

settings = Settings()
```

---

## storage/database.py — Postgres (asyncpg, SSL, SessionDep)

```python
from typing import Annotated, AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from config import settings
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = settings.database.url
if DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_async_url = DATABASE_URL
_needs_ssl = "sslmode=" in _async_url
if _needs_ssl:
    parsed = urlparse(_async_url)
    qs = parse_qs(parsed.query)
    qs.pop("sslmode", None)
    new_query = urlencode(qs, doseq=True)
    _async_url = urlunparse(parsed._replace(query=new_query))

engine = create_async_engine(
    _async_url,
    echo=True,
    connect_args={"ssl": True} if _needs_ssl else {},
)
sync_url = DATABASE_URL.replace("postgresql+asyncpg", "postgresql", 1)
sync_engine = create_engine(sync_url, echo=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

---

## worker.py — Redis (broker, backend, SSL for rediss)

```python
import ssl
from urllib.parse import urlparse
from celery import Celery
from kombu import Queue
from config import settings

redis_ssl_options = None
if urlparse(settings.redis.url).scheme == "rediss":
    redis_ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

worker = Celery(
    "backend",
    broker=settings.redis.url,
    backend=settings.redis.url,
)
worker.autodiscover_tasks(["tasks"])
worker.conf.broker_use_ssl = redis_ssl_options
worker.conf.redis_backend_use_ssl = redis_ssl_options
worker.conf.task_queues = (Queue("celery"),)
```

---

## lib/zendesk_llm_limiter.py — Redis LLM cap (Lua atomic)

```python
import uuid
import redis
from config import settings

_LIMIT_TICKETS_PER_RUN = 5
_TTL_SECONDS = 600
_RUN_ID_KEY = "zendesk:llm_limit:run_id"

def _run_id() -> str | None:
    try:
        r = redis.from_url(settings.redis.url)
        run_id = r.get(_RUN_ID_KEY)
        return run_id.decode() if isinstance(run_id, (bytes, bytearray)) else run_id
    except Exception:
        return None

def init_zendesk_llm_limit(*, reset: bool) -> None:
    if (settings.environment or "").lower() in ("test", "prod", "production"):
        return
    try:
        r = redis.from_url(settings.redis.url)
        if reset:
            r.delete(_RUN_ID_KEY)
        run_id_value = str(uuid.uuid4())
        if r.set(_RUN_ID_KEY, run_id_value, ex=_TTL_SECONDS, nx=not reset) is None:
            return
        count_key = f"zendesk:llm_limit:{run_id_value}:count"
        r.set(count_key, 0, ex=_TTL_SECONDS, nx=False)
    except Exception:
        pass

def should_run_llm_for_ticket(ticket_id: int) -> bool:
    if (settings.environment or "").lower() in ("test", "prod", "production"):
        return True
    active_run_id = _run_id()
    if not active_run_id:
        return False
    ticket_key = f"zendesk:llm_limit:{active_run_id}:ticket:{ticket_id}"
    count_key = f"zendesk:llm_limit:{active_run_id}:count"
    lua = """
    local ticket_key, count_key = KEYS[1], KEYS[2]
    local limit, ttl = tonumber(ARGV[1]), tonumber(ARGV[2])
    if redis.call('EXISTS', ticket_key) == 1 then return 0 end
    local new_count = redis.call('INCR', count_key)
    redis.call('EXPIRE', count_key, ttl)
    if new_count > limit then return 0 end
    redis.call('SET', ticket_key, '1', 'EX', ttl)
    return 1
    """
    try:
        r = redis.from_url(settings.redis.url)
        allowed = r.eval(lua, 2, ticket_key, count_key, _LIMIT_TICKETS_PER_RUN, _TTL_SECONDS)
        return int(allowed) == 1
    except Exception:
        return True
```

---

## tasks/_async.py — run_async_task (dispose engine after coro)

```python
import asyncio
from collections.abc import Coroutine
from typing import TypeVar
from storage.database import engine

T = TypeVar("T")

async def _run_and_dispose(coro: Coroutine[object, object, T]) -> T:
    try:
        return await coro
    finally:
        await engine.dispose()

def run_async_task(coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(_run_and_dispose(coro))
```

---

## services/zendesk_service.py — ZendeskService (DB + OpenAI + Redis limiter)

```python
import asyncio
from datetime import datetime, timezone
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Assumes: parse_ticket_payload, TicketDetailWithTimestamps, ZendeskClient,
# summarize_ticket_to_motion, should_run_llm_for_ticket,
# Motion, ZendeskTicket, ZendeskWebhook, MotionResult, MotionStatus, TicketImportStatus.
# Helpers: _map_result("carried"|"defeated") -> MotionResult, _map_status("ongoing"|"resolved") -> MotionStatus.

class ZendeskService:
    async def _upsert_motion_from_ticket_payload(self, session: AsyncSession, payload: dict) -> Motion:
        parsed_payload = parse_ticket_payload(payload)
        detail = parsed_payload.ticket or TicketDetailWithTimestamps()
        ticket_id = str(detail.id or "")
        if not ticket_id:
            raise ValueError("Ticket payload missing id")
        source_key = f"zendesk.tickets.{ticket_id}"
        existing = (await session.exec(
            select(Motion).where(Motion.source_key == source_key)
        )).first()
        title, motion_description = detail.subject or "(No subject)", detail.description or "(No description)"
        result, status = MotionResult.unknown, _map_status(detail.status)

        if should_run_llm_for_ticket(int(ticket_id)):
            full_conversation = await ZendeskClient().resolve_ticket_conversation_payload(ticket_id, payload)
            summary = await asyncio.to_thread(summarize_ticket_to_motion, full_conversation)
            title = summary.title or detail.subject
            motion_description = summary.description or detail.description
            result = _map_result(summary.result)
            status = _map_status(summary.status)

        if existing:
            existing.title, existing.description, existing.result, existing.status = title, motion_description, result, status
            session.add(existing)
            await session.commit()
            return existing
        motion = Motion(source_key=source_key, title=title, description=motion_description, result=result, status=status)
        session.add(motion)
        await session.commit()
        return motion

    async def process_webhook_event(self, session: AsyncSession, webhook_event_id: int) -> None:
        event = await session.get(ZendeskWebhook, webhook_event_id)
        if not event or event.processed_at:
            return
        payload = event.payload or {}
        parsed = parse_ticket_payload(payload)
        ticket_id = parsed.ticket.id if parsed.ticket else None
        if ticket_id is None:
            event.error = "Payload missing ticket id"
            session.add(event)
            await session.commit()
            return
        try:
            await self._upsert_motion_from_ticket_payload(session, payload)
            event.processed_at = datetime.now(timezone.utc)
            session.add(event)
            await session.commit()
            synced = await self.sync_ticket(session, int(ticket_id))
            if synced.id:
                await self.process_ticket(session, synced.id)
        except Exception as e:
            await session.rollback()
            event.error = str(e)
            session.add(event)
            await session.commit()
            raise

    async def process_ticket(self, session: AsyncSession, ticket_id: int, force_reprocess: bool = False) -> None:
        row = await session.get(ZendeskTicket, ticket_id)
        if not row or (row.status == TicketImportStatus.processed.value and not force_reprocess):
            return
        try:
            await self._upsert_motion_from_ticket_payload(session, row.payload)
            row.status = TicketImportStatus.processed.value
            row.error = None
        except Exception as e:
            row.status = TicketImportStatus.error.value
            row.error = str(e)
        session.add(row)
        await session.commit()

    async def sync_ticket(self, session: AsyncSession, zendesk_ticket_id: int) -> ZendeskTicket:
        ticket = (await session.exec(select(ZendeskTicket).where(ZendeskTicket.zendesk_ticket_id == zendesk_ticket_id))).first() or ZendeskTicket(zendesk_ticket_id=zendesk_ticket_id, payload={}, audit_events={}, status=TicketImportStatus.pending.value)
        full_ticket = await ZendeskClient().get_ticket_with_side_conversations(ticket.zendesk_ticket_id)
        ticket.payload = full_ticket
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket
```

---

## tasks/jobs.py — Task + run_async_task pattern

```python
from worker import worker
from tasks._async import run_async_task
from storage.database import engine
from sqlmodel.ext.asyncio.session import AsyncSession

@worker.task(bind=True, max_retries=0)
def process_webhook(self, webhook_id: int) -> None:
    run_async_task(_process_webhook(webhook_id))

async def _process_webhook(webhook_id: int) -> None:
    async with AsyncSession(engine, autoflush=False, autocommit=False, expire_on_commit=False) as session:
        await ZendeskService().process_webhook_event(session, webhook_id)
```

---

## Chord pipeline (fan-out per id, then finalize)

```python
from celery import chain, chord, group

chord(
    group([
        chain(sync_item.s(id), process_item.s())
        for id in ids
    ])
)(update_run.s(run_id))
```

---

## FastAPI route — Sync (create run, delay)

```python
run = JobRun(status="pending")
session.add(run)
await session.commit()
await session.refresh(run)
sync_job.delay(run.id)
return run
```

---

## FastAPI route — Webhook (store, delay, 202)

```python
event = WebhookEvent(payload=await request.json())
session.add(event)
await session.commit()
await session.refresh(event)
process_webhook.delay(event.id)
return {}
```

---

## Models — JobRun and WebhookEvent

```python
from enum import Enum
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

class WebhookEvent(SQLModel, table=True):
    __tablename__ = "webhook_events"
    id: int | None = Field(default=None, primary_key=True)
    payload: dict = Field(default_factory=dict)
    error: str | None = None
```

---

## Run commands

```bash
# Terminal 1: Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Worker
REDIS_URL=redis://localhost:6379/0 celery -A worker worker -Q celery -l info

# Terminal 3: FastAPI
REDIS_URL=redis://localhost:6379/0 uvicorn api:app --reload --port 8000
```
