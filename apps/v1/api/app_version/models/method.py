"""Database methods for app version config."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.utils import constant_variable as constant


class AppVersionMethod:
    """CRUD helpers for AppVersionConfig."""

    def __init__(self, model) -> None:
        self.model = model

    async def find_by_app_type_and_platform(
        self,
        db: AsyncSession,
        app_type: str,
        platform: str,
        deleted_at=constant.STATUS_NULL,
        active_only: bool = True,
    ):
        """Return version config for app_type + platform."""
        stmt = select(self.model).where(
            self.model.app_type == app_type,
            self.model.platform == platform,
            self.model.deleted_at == deleted_at,
        )
        if active_only:
            stmt = stmt.where(self.model.is_active == constant.STATUS_TRUE)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def find_all_active(self, db: AsyncSession, deleted_at=constant.STATUS_NULL):
        """Return all active version configs."""
        stmt = select(self.model).where(
            self.model.deleted_at == deleted_at,
            self.model.is_active == constant.STATUS_TRUE,
        )
        result = await db.execute(stmt)
        return result.scalars().all()
