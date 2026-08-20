"""Shared helpers to validate JWT sessions via DB jti."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.model import Session
from config.db_session import session_factory


async def is_session_active(db: AsyncSession, token_data: dict) -> bool:
    """
    Return True if JWT jti still exists in sessions table for this user/driver.

    Admin tokens do not use session-jti tracking.
    """
    if token_data.get("user_type") == "admin":
        return True

    jti = token_data.get("jti")
    user_id = token_data.get("user_id")
    user_type = token_data.get("user_type")

    if not jti or not user_id or user_type not in (
        UserTypeEnum.CUSTOMER.value,
        UserTypeEnum.DRIVER.value,
    ):
        return False

    stmt = select(Session).where(
        Session.session_id == jti,
        Session.deleted_at.is_(None),
    )
    if user_type == UserTypeEnum.DRIVER.value:
        stmt = stmt.where(Session.driver_id == user_id)
    else:
        stmt = stmt.where(Session.user_id == user_id)

    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def validate_token_session(token_data: dict) -> bool:
    """Open a short-lived DB session and validate active jti."""
    async with session_factory() as db:
        return await is_session_active(db, token_data)
