"""This module contains database operations methods for the vehicle."""

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.utils import constant_variable as constant


class VehicleMethod:
    """This class defines methods to vehicle."""

    def __init__(self, model) -> None:
        self.model = model

    async def find_by_driver_id(
        self, db: AsyncSession, driver_id: int, deleted_at=constant.STATUS_NULL
    ):
        """This function will returns the vehicle object using driver id"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.driver_id == driver_id, self.model.deleted_at == deleted_at
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_all_by_driver_id(
        self, db: AsyncSession, driver_id: int, deleted_at=constant.STATUS_NULL
    ):
        """Return all vehicles for a driver."""
        stmt = select(self.model).where(
            self.model.driver_id == driver_id, self.model.deleted_at == deleted_at
        )
        result = await db.execute(stmt)
        return result.scalars().all()

