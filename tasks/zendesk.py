from datetime import datetime

from celery import chain, chord, group
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings
from models.zendesk import SyncRequest, SyncRequestStatus, ZendeskWebhook
from services.zendesk_service import ZendeskService
from storage.database import engine
from tasks._async import run_async_task
from worker import worker


@worker.task(bind=True, max_retries=0)
def process_zendesk_webhook(self, webhook_id: int) -> None:
    if not settings.zendesk_webhook_enabled:
        return
    try:
        run_async_task(_process_zendesk_webhook(webhook_id))
    except Exception as e:
        run_async_task(_mark_webhook_error(webhook_id, str(e)))
        raise


async def _process_zendesk_webhook(webhook_id: int) -> None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        await ZendeskService().process_webhook_event(session, webhook_id)


async def _mark_webhook_error(webhook_id: int, error: str) -> None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        event = await session.get(ZendeskWebhook, webhook_id)
        if event:
            event.error = error
            session.add(event)
            await session.commit()


@worker.task(bind=True, max_retries=0)
def sync_zendesk_tickets(self, sync_request_id: int) -> None:
    run_async_task(_sync_zendesk_tickets_for_request(sync_request_id))


async def _sync_zendesk_tickets_for_request(sync_request_id: int) -> None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        run = await session.get(SyncRequest, sync_request_id)
        if not run:
            return
        run.status = SyncRequestStatus.running.value
        await session.commit()
        start_time = None
        if run.start_date:
            start_time = int(
                datetime.combine(run.start_date, datetime.min.time()).timestamp()
            )
        zendesk_ticket_ids = await ZendeskService().sync_ticket_events(
            session, start_time=start_time
        )
        if not zendesk_ticket_ids:
            run.status = SyncRequestStatus.success.value
            run.finished_at = datetime.utcnow()
            session.add(run)
            await session.commit()
            return
        chord(
            group(
                [
                    chain(
                        sync_zendesk_ticket.s(zid),
                        process_zendesk_ticket.s(),
                    )
                    for zid in zendesk_ticket_ids
                ]
            )
        )(update_sync_request.s(sync_request_id))


@worker.task(bind=True, max_retries=0)
def sync_zendesk_ticket(self, zendesk_ticket_id: int) -> int | None:
    return run_async_task(_sync_zendesk_ticket(zendesk_ticket_id))


async def _sync_zendesk_ticket(zendesk_ticket_id: int) -> int | None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        ticket = await ZendeskService().sync_ticket(session, zendesk_ticket_id)
        return ticket.id if ticket else None


@worker.task(bind=True, max_retries=0)
def process_zendesk_ticket(self, ticket_id: int | None) -> int | None:
    if ticket_id is None:
        return None
    run_async_task(_process_zendesk_ticket(ticket_id))
    return ticket_id


async def _process_zendesk_ticket(ticket_id: int) -> None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        await ZendeskService().process_ticket(session, ticket_id)


@worker.task(bind=True, max_retries=0)
def update_sync_request(
    self, updated_ticket_ids: list[int | None], sync_request_id: int
) -> None:
    run_async_task(_update_sync_request(updated_ticket_ids, sync_request_id))


async def _update_sync_request(
    updated_ticket_ids: list[int | None], sync_request_id: int
) -> None:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        run = await session.get(SyncRequest, sync_request_id)
        if run:
            run.status = SyncRequestStatus.success.value
            run.finished_at = datetime.utcnow()
            run.updated_ticket_ids = updated_ticket_ids
            session.add(run)
            await session.commit()
