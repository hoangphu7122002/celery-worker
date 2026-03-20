from openai import OpenAI
from pydantic import BaseModel

from config import settings

TICKET_TO_MOTION_PROMPT_TEMPLATE = """Summarize this Zendesk support ticket and its full conversation (main thread and side conversations) into a motion-style record.

---

{conversation_text}

---

Respond with exactly these four fields, one per line:
title: <Short, clear motion title, no ticket ID or numbering>
description: <Concise summary, key points and outcome, 2–5 sentences>
result: one of carried, defeated, unknown
status: one of ongoing, resolved, unknown"""


class TicketMotionSummary(BaseModel):
    title: str
    description: str
    result: str  # "carried" | "defeated" | "unknown"
    status: str  # "ongoing" | "resolved" | "unknown"


def _build_conversation_text(payload: dict) -> str:
    """Flatten ticket + comments + side convs into text."""
    parts: list[str] = []
    ticket = payload.get("ticket") or {}
    if isinstance(ticket, dict):
        parts.append(f"Subject: {ticket.get('subject', '')}")
        parts.append(f"Description: {ticket.get('description', '')}")
        parts.append(f"Status: {ticket.get('status', '')}")
    for c in payload.get("comments", []) or []:
        if isinstance(c, dict) and c.get("body"):
            parts.append(f"Comment: {c.get('body')}")
    for sc in payload.get("side_conversations", []) or []:
        if isinstance(sc, dict):
            for evt in sc.get("side_conversation_events", []) or []:
                if isinstance(evt, dict) and evt.get("body"):
                    parts.append(f"Side: {evt.get('body')}")
    return "\n\n".join(parts) or "(No content)"


def _parse_llm_summary_response(raw: str) -> TicketMotionSummary:
    """Parse LLM response into TicketMotionSummary."""
    title = "Unknown"
    description = ""
    result = "unknown"
    status = "unknown"
    for line in raw.strip().split("\n"):
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("description:"):
            description = line.split(":", 1)[1].strip()
        elif line.lower().startswith("result:"):
            r = line.split(":", 1)[1].strip().lower()
            if r in ("carried", "defeated", "unknown"):
                result = r
        elif line.lower().startswith("status:"):
            s = line.split(":", 1)[1].strip().lower()
            if s in ("ongoing", "resolved", "unknown"):
                status = s
    return TicketMotionSummary(title=title, description=description, result=result, status=status)


def summarize_ticket_to_motion(
    full_conversation: dict,
    model: str | None = None,
) -> TicketMotionSummary:
    """Summarize ticket conversation into Motion fields via OpenAI."""
    model = model or settings.conversation_model
    if not settings.openai_api_key:
        ticket = full_conversation.get("ticket") or {}
        return TicketMotionSummary(
            title=str(ticket.get("subject", "Unknown"))[:200],
            description=str(ticket.get("description", ""))[:500],
            result="unknown",
            status="unknown",
        )
    conversation_text = _build_conversation_text(full_conversation)
    content = TICKET_TO_MOTION_PROMPT_TEMPLATE.format(conversation_text=conversation_text)
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
    )
    raw = completion.choices[0].message.content if completion.choices else None
    if not raw:
        raise ValueError("LLM returned no content")
    return _parse_llm_summary_response(raw)
