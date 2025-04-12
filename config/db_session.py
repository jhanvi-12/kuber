from contextlib import asynccontextmanager
from contextvars import ContextVar
from enum import Enum
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.expression import Delete, Insert, Update

from config import env_config

session_context: ContextVar[str] = ContextVar("session_context")

# ✅ DATABASE CONFIGURATION
SQLALCHEMY_DATABASE_URL = f"mysql+aiomysql://{env_config.DATABASE_USER}:{env_config.DATABASE_PASSWORD}@{env_config.DATABASE_HOST}:{env_config.DATABASE_PORT}/{env_config.DATABASE_NAME}"

class EngineType(Enum):
    WRITER = "writer"
    READER = "reader"

engines = {
    EngineType.WRITER: create_async_engine(SQLALCHEMY_DATABASE_URL, pool_recycle=3600),
    EngineType.READER: create_async_engine(SQLALCHEMY_DATABASE_URL, pool_recycle=3600),
}

class RoutingSession(Session):
    def get_bind(self, mapper=None, clause=None, **kw):
        if self._flushing or isinstance(clause, (Update, Delete, Insert)):
            return engines[EngineType.WRITER].sync_engine
        return engines[EngineType.READER].sync_engine

_async_session_factory = async_sessionmaker(
    class_=AsyncSession,
    sync_session_class=RoutingSession,
    expire_on_commit=False,
)

session = async_scoped_session(
    session_factory=_async_session_factory,
    scopefunc=lambda: None,
)

class Base(DeclarativeBase):
    pass

@asynccontextmanager
async def session_factory() -> AsyncGenerator[AsyncSession, None]:
    _session = _async_session_factory()
    try:
        yield _session
    finally:
        await _session.close()
