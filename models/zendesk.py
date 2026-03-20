from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class SyncRequestStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class TicketImportStatus(str, Enum):
    pending = "pending"
    processed = "processed"
    error = "error"


class MotionResult(str, Enum):
    carried = "carried"
    defeated = "defeated"
    unknown = "unknown"


class MotionStatus(str, Enum):
    ongoing = "ongoing"
    resolved = "resolved"
    unknown = "unknown"


class ZendeskWebhook(SQLModel, table=True):
    __tablename__ = "zendesk_webhooks"
    id: int | None = Field(default=None, primary_key=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    processed_at: datetime | None = None
    error: str | None = None


class ZendeskTicket(SQLModel, table=True):
    __tablename__ = "zendesk_tickets"
    id: int | None = Field(default=None, primary_key=True)
    zendesk_ticket_id: int = Field(unique=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    audit_events: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    status: str = Field(default="pending")
    error: str | None = None


class SyncRequest(SQLModel, table=True):
    __tablename__ = "sync_requests"
    id: int | None = Field(default=None, primary_key=True)
    status: str = Field(default="pending")
    start_date: date | None = None
    updated_ticket_ids: list[int] | None = Field(default=None, sa_column=Column(JSONB))
    finished_at: datetime | None = None


class Motion(SQLModel, table=True):
    __tablename__ = "motions"
    id: int | None = Field(default=None, primary_key=True)
    source_key: str | None = None
    title: str = ""
    description: str = ""
    result: str = Field(default="unknown")
    status: str = Field(default="unknown")
