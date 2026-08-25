
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from config.db_session import session_factory


# Define FastAPI Dependencyasync def
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
