import base64

import httpx
from pydantic import BaseModel

from config import settings


class TicketDetailWithTimestamps(BaseModel):
    id: int | None = None
    subject: str | None = None
    description: str | None = None
    status: str | None = None


class ParsedTicketPayload(BaseModel):
    ticket: TicketDetailWithTimestamps | None = None


def _auth_header() -> str:
    credentials = f"{settings.zendesk_email}/token:{settings.zendesk_api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def parse_ticket_payload(payload: dict) -> ParsedTicketPayload:
    """Parse Zendesk webhook or ticket payload into structured form."""
    ticket_data = payload.get("ticket") or payload
    ticket = None
    if isinstance(ticket_data, dict):
        ticket = TicketDetailWithTimestamps(
            id=ticket_data.get("id"),
            subject=ticket_data.get("subject"),
            description=ticket_data.get("description"),
            status=ticket_data.get("status"),
        )
    return ParsedTicketPayload(ticket=ticket)


class ZendeskClient:
    def __init__(self) -> None:
        self._base_url = f"https://{settings.zendesk_subdomain}.zendesk.com/api/v2"
        self._headers = {
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
        }

    async def get_ticket_with_side_conversations(self, ticket_id: int) -> dict:
        """Fetch full ticket with comments and side conversations; return payload dict."""
        if not settings.zendesk_subdomain or not settings.zendesk_api_token:
            return {"ticket": {"id": ticket_id, "subject": "", "description": "", "status": "new"}}
        async with httpx.AsyncClient() as client:
            ticket_resp = await client.get(
                f"{self._base_url}/tickets/{ticket_id}.json",
                headers=self._headers,
            )
            ticket_resp.raise_for_status()
            data = ticket_resp.json()
            ticket = data.get("ticket", {})
            comments_resp = await client.get(
                f"{self._base_url}/tickets/{ticket_id}/comments.json",
                headers=self._headers,
            )
            comments = []
            if comments_resp.status_code == 200:
                comments = comments_resp.json().get("comments", [])
            result: dict = {"ticket": ticket, "comments": comments}
            try:
                sc_resp = await client.get(
                    f"{self._base_url}/tickets/{ticket_id}/side_conversations",
                    headers=self._headers,
                )
                if sc_resp.status_code == 200:
                    result["side_conversations"] = sc_resp.json().get("side_conversations", [])
            except Exception:
                result["side_conversations"] = []
            return result

    async def get_ticket_events(
        self, start_time: int | None = None, end_time: int | None = None
    ) -> list[int]:
        """Paginate incremental ticket events; return list of touched ticket ids."""
        if not settings.zendesk_subdomain or not settings.zendesk_api_token:
            return []
        touched_ids: list[int] = []
        url = f"{self._base_url}/incremental/tickets.json"
        params: dict = {}
        if start_time:
            params["start_time"] = start_time
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(url, headers=self._headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                for t in data.get("tickets", []):
                    tid = t.get("id")
                    if tid:
                        touched_ids.append(int(tid))
                if data.get("end_of_stream"):
                    break
                next_page = data.get("next_page")
                if not next_page:
                    break
                url = next_page
                params = {}
        return touched_ids

    async def resolve_ticket_conversation_payload(self, ticket_id: str, payload: dict) -> dict:
        """Resolve full conversation from payload or fetch from API."""
        if payload.get("comments") and payload.get("ticket"):
            return payload
        full = await self.get_ticket_with_side_conversations(int(ticket_id))
        return full
