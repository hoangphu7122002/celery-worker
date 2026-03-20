from datetime import date

from fastapi import Body, FastAPI, HTTPException, Request
from pydantic import BaseModel

from config import settings
from lib.zendesk_llm_limiter import init_zendesk_llm_limit
from models.zendesk import SyncRequest, SyncRequestStatus, ZendeskWebhook
from storage.database import SessionDep
from tasks.jobs import process_job
from tasks.zendesk import process_zendesk_webhook, sync_zendesk_tickets

app = FastAPI()


@app.post("/jobs/{job_id}")
def trigger_job(job_id: int):
    """Enqueue task; worker picks it up from Redis."""
    result = process_job.delay(job_id)
    return {"task_id": result.id, "job_id": job_id}


class SyncTicketsBody(BaseModel):
    start_date: date | None = None


@app.post("/zendesk/webhooks")
async def zendesk_webhook(request: Request, session: SessionDep) -> dict:
    if not settings.zendesk_webhook_enabled:
        raise HTTPException(status_code=403, detail="Zendesk webhook is disabled")
    init_zendesk_llm_limit(reset=False)
    event = ZendeskWebhook(payload=await request.json())
    session.add(event)
    await session.commit()
    await session.refresh(event)
    process_zendesk_webhook.delay(event.id)
    return {}


@app.post("/zendesk/tickets/sync")
async def sync_zendesk_tickets_route(
    session: SessionDep,
    body: SyncTicketsBody | None = Body(default=None),
):
    body = body or SyncTicketsBody()
    init_zendesk_llm_limit(reset=True)
    run = SyncRequest(
        status=SyncRequestStatus.pending.value,
        start_date=body.start_date,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    sync_zendesk_tickets.delay(run.id)
    return run


@app.get("/zendesk/sync-requests/{sync_request_id}")
async def get_sync_request(
    sync_request_id: int,
    session: SessionDep,
):
    run = await session.get(SyncRequest, sync_request_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sync request not found")
    return run
