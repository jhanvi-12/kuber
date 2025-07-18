"""This module contains database operations methods for drivers."""

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.v1.api.vehicle.models.model import Vehicle
from core.utils import constant_variable as constant
from apps.v1.api.ride.models.attribute import RideStatusEnum


class DriverMethod:
    """This class defines methods to driver."""

    def __init__(self, model) -> None:
        self.model = model

    async def fecth_all_active_drivers_by_ride(
        self, db: AsyncSession, ride_type, deleted_at=constant.STATUS_NULL
    ):
        """This function will returns the user object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).join(
                Vehicle,
                self.model.id == Vehicle.driver_id,
            ).where(
                self.model.is_active == constant.STATUS_TRUE,
                self.model.deleted_at == deleted_at,
                Vehicle.vehicle_type == ride_type,
                Vehicle.deleted_at == deleted_at,
            )
            result = await db.execute(stmt)
            return result.scalars().all()

    async def get_driver_by_id(self, db: AsyncSession, driver_id: int):
        """Fetch a driver by their ID."""
        async with db:
            stmt = select(self.model).where(
                self.model.id == driver_id,
                self.model.deleted_at == constant.STATUS_NULL,
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def get_ride_by_driver(
        self, db: AsyncSession, driver_id: int, ride_id: int
    ):
        """Fetch a ride by driver ID and ride ID."""
        async with db:
            stmt = select(self.model).where(
                self.model.id == ride_id,
                self.model.driver_id == driver_id,
                self.model.status == RideStatusEnum.ACCEPTED.value,
                self.model.deleted_at == constant.STATUS_NULL,
            )
            result = await db.execute(stmt)
            return result.scalars().first()

