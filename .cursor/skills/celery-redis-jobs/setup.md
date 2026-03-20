# Worker + FastAPI Setup (from scratch)

Complete setup so FastAPI can trigger Celery tasks. All code is self-contained.

---

## 1. Project layout

```
my-project/
├── pyproject.toml
├── .env.example
├── config.py
├── worker.py
├── api.py
├── tasks/
│   ├── __init__.py
│   └── jobs.py
└── app/           # optional: move routes here
```

---

## 2. config.py — Settings with REDIS_URL

```python
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(".env", override=False)

class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}
    redis_url: str = "redis://localhost:6379/0"

    @property
    def redis(self):
        return type("RedisSettings", (), {"url": self.redis_url})()

settings = Settings()
```

---

## 3. worker.py — Celery app

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
    "myapp",
    broker=settings.redis.url,
    backend=settings.redis.url,
)
worker.autodiscover_tasks(["tasks"])
worker.conf.broker_use_ssl = redis_ssl_options
worker.conf.redis_backend_use_ssl = redis_ssl_options
worker.conf.task_queues = (Queue("celery"),)
```

---

## 4. tasks/jobs.py — Task that FastAPI will trigger

```python
from worker import worker

@worker.task(bind=True, max_retries=0)
def process_job(self, job_id: int) -> int:
    """Worker runs this when FastAPI calls process_job.delay(job_id)."""
    # Do work here
    return job_id
```

---

## 5. api.py — FastAPI app that triggers worker

```python
from fastapi import FastAPI
from tasks.jobs import process_job

app = FastAPI()

@app.post("/jobs/{job_id}")
def trigger_job(job_id: int):
    """Enqueue task; worker picks it up from Redis."""
    result = process_job.delay(job_id)
    return {"task_id": result.id, "job_id": job_id}
```

---

## 6. Run commands (three terminals)

**Terminal 1 — Redis:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
# Or: redis-server
```

**Terminal 2 — Worker:**
```bash
export REDIS_URL=redis://localhost:6379/0
celery -A worker worker -Q celery -l info
```

**Terminal 3 — FastAPI:**
```bash
export REDIS_URL=redis://localhost:6379/0
uvicorn api:app --reload --port 8000
```

---

## 7. Trigger from HTTP

```bash
curl -X POST http://localhost:8000/jobs/123
# Response: {"task_id":"...", "job_id":123}
# Worker terminal shows: Task tasks.jobs.process_job[xxx] received
```

---

## 8. .env.example

```
REDIS_URL=redis://localhost:6379/0
```

---

## 9. PostgreSQL (optional, full stack)

Add `DATABASE_URL` to config. Full code: [reference.md](.cursor/skills/celery-redis-jobs/reference.md) (storage/database.py, config.py).

**config.py** — add `database_url: str` and `@property def database`: `DatabaseSettings(url=...)`.

**storage/database.py** — convert `postgresql://` to `postgresql+asyncpg://`; strip `sslmode=` and use `connect_args={"ssl": True}` for Azure. Create `engine`, `get_session`, `SessionDep`.

**Local dev**: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:alpine`.

**.env.example** — add `DATABASE_URL=postgresql://user@localhost:5432/dbname`.

---

## 10. OpenAI (optional, full stack)

Add `OPENAI_API_KEY`, `OPENAI_BASE_URL` (optional, e.g. OpenRouter), `EXTRACTION_MODEL`, `CONVERSATION_MODEL`. Full code: [reference.md](.cursor/skills/celery-redis-jobs/reference.md) (config, ZendeskService with OpenAI).

```python
from openai import OpenAI

client = OpenAI(api_key=settings.openai.api_key, base_url=settings.openai.base_url)
completion = client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}])
raw = completion.choices[0].message.content
```

**.env.example** — add `OPENAI_API_KEY=sk-...`, `OPENAI_BASE_URL=` (optional), `CONVERSATION_MODEL=gpt-4o-mini`.

---

## 11. docker-compose.yml (optional)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

Run: `docker compose up -d redis`, then start worker and API on host with `REDIS_URL=redis://localhost:6379/0`.
