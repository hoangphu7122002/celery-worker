import asyncio
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from clients.zendesk_client import (
    ZendeskClient,
    parse_ticket_payload,
    TicketDetailWithTimestamps,
)
from lib.zendesk_llm_limiter import should_run_llm_for_ticket
from models.zendesk import (
    Motion,
    ZendeskTicket,
    ZendeskWebhook,
    TicketImportStatus,
)
from services.openai_summary import summarize_ticket_to_motion


def _map_result(val: str) -> str:
    if val and val.lower() in ("carried", "defeated"):
        return val.lower()
    return "unknown"


def _map_status(val: str | None) -> str:
    if val and val.lower() in ("ongoing", "resolved"):
        return val.lower()
    return "unknown"


class ZendeskService:
    async def _upsert_motion_from_ticket_payload(
        self, session: AsyncSession, payload: dict
    ) -> Motion:
        parsed = parse_ticket_payload(payload)
        detail = parsed.ticket or TicketDetailWithTimestamps()
        ticket_id = str(detail.id or "")
        if not ticket_id:
            raise ValueError("Ticket payload missing id")
        source_key = f"zendesk.tickets.{ticket_id}"
        existing = (
            await session.exec(select(Motion).where(Motion.source_key == source_key))
        ).first()
        title = detail.subject or "(No subject)"
        motion_description = detail.description or "(No description)"
        result = _map_status(detail.status)
        status = _map_status(detail.status)

        if should_run_llm_for_ticket(int(ticket_id)):
            full_conversation = await ZendeskClient().resolve_ticket_conversation_payload(
                ticket_id, payload
            )
            summary = await asyncio.to_thread(
                summarize_ticket_to_motion, full_conversation
            )
            title = summary.title or detail.subject or title
            motion_description = summary.description or detail.description or motion_description
            result = _map_result(summary.result)
            status = _map_status(summary.status)

        if existing:
            existing.title = title
            existing.description = motion_description
            existing.result = result
            existing.status = status
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return existing
        motion = Motion(
            source_key=source_key,
            title=title,
            description=motion_description,
            result=result,
            status=status,
        )
        session.add(motion)
        await session.commit()
        await session.refresh(motion)
        return motion

    async def process_webhook_event(
        self, session: AsyncSession, webhook_event_id: int
    ) -> None:
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
            event.processed_at = datetime.utcnow()
            session.add(event)
            await session.commit()
            synced = await self.sync_ticket(session, int(ticket_id))
            if synced and synced.id:
                await self.process_ticket(session, synced.id)
        except Exception as e:
            await session.rollback()
            event.error = str(e)
            session.add(event)
            await session.commit()
            raise

    async def process_ticket(
        self,
        session: AsyncSession,
        ticket_id: int,
        force_reprocess: bool = False,
    ) -> None:
        row = await session.get(ZendeskTicket, ticket_id)
        if not row or (
            row.status == TicketImportStatus.processed.value and not force_reprocess
        ):
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

    async def sync_ticket(
        self, session: AsyncSession, zendesk_ticket_id: int
    ) -> ZendeskTicket | None:
        result = (
            await session.exec(
                select(ZendeskTicket).where(
                    ZendeskTicket.zendesk_ticket_id == zendesk_ticket_id
                )
            )
        ).first()
        ticket = result or ZendeskTicket(
            zendesk_ticket_id=zendesk_ticket_id,
            payload={},
            audit_events={},
            status=TicketImportStatus.pending.value,
        )
        full_ticket = await ZendeskClient().get_ticket_with_side_conversations(
            ticket.zendesk_ticket_id
        )
        ticket.payload = full_ticket
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

    async def sync_ticket_events(
        self,
        session: AsyncSession,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[int]:
        """Fetch ticket events from Zendesk API; return touched ticket ids."""
        touched = await ZendeskClient().get_ticket_events(start_time, end_time)
        for tid in touched:
            ticket = (
                await session.exec(
                    select(ZendeskTicket).where(
                        ZendeskTicket.zendesk_ticket_id == tid
                    )
                )
            ).first()
            if not ticket:
                ticket = ZendeskTicket(
                    zendesk_ticket_id=tid,
                    payload={},
                    audit_events={},
                    status=TicketImportStatus.pending.value,
                )
                session.add(ticket)
        await session.commit()
        return touched
