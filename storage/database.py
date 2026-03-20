from typing import Annotated, AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import settings
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine
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


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(
        engine, autoflush=False, autocommit=False, expire_on_commit=False
    ) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
