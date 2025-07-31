"""This module is used to implement driver subscription plans functionality."""

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.utils import constant_variable as constant

class PlansMethod:
    """This class defines methods for plans."""

    def __init__(self, model) -> None:
        self.model = model

    async def find_plan_by_driver_id(
        self, db: AsyncSession, driver_id: int, deleted_at = constant.STATUS_NULL
    ):
        """This function will return the user object by email asynchronously."""
        async with db:
            stmt = select(self.model).where(
                self.model.driver_id == driver_id,
                self.model.deleted_at == deleted_at,
                self.model.is_expired == constant.STATUS_FALSE,
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_plan_by_driver_id_list(
        self, db: AsyncSession, driver_ids: list, deleted_at = constant.STATUS_NULL
    ):
        """This function will return the user object by email asynchronously."""
        async with db:
            stmt = select(self.model).where(
                self.model.id.in_(driver_ids),
                self.model.deleted_at == deleted_at,
            )
            result = await db.execute(stmt)
            return result.scalars().all()

    async def find_all_active_plans(
        self, db: AsyncSession, deleted_at = constant.STATUS_NULL
    ):
        """This function will return all active plans."""
        async with db:
            stmt = select(self.model).where(
                self.model.deleted_at == deleted_at,
                self.model.is_expired == constant.STATUS_FALSE,
            )
            result = await db.execute(stmt)
            return result.scalars().all()
