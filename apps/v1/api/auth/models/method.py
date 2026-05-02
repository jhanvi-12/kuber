"""This module contains database operations methods."""

from datetime import datetime
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apps.v1.api.ride.models.attribute import RideStatusEnum
from core.utils import constant_variable as constant


class UserAuthMethod:
    """This class defines methods to authenticate users."""

    def __init__(self, model) -> None:
        self.model = model

    async def find_by_id(
        self, db: AsyncSession, user_id: int, deleted_at=constant.STATUS_NULL
    ):
        """This function will returns the user object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.id == user_id, self.model.deleted_at == deleted_at
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_driver_id(
        self, db: AsyncSession, driver_id: int, deleted_at=constant.STATUS_NULL
    ):
        """This function will returns the driver object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.driver_id == driver_id, self.model.deleted_at == deleted_at
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_session_id(self, db: AsyncSession, driver_id, user_id, session_id: str):
        """This function will return the user session object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.user_id == user_id,
                self.model.driver_id == driver_id,
                self.model.session_id == session_id
            )

            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_email(
        self, db: AsyncSession, email: str, deleted_at=constant.STATUS_NULL
    ):
        """This function will return the user object by email asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.email == email, self.model.deleted_at == deleted_at
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_verified_email_user(
        self, db: AsyncSession, email: str, deleted_at=constant.STATUS_NULL
    ):
        """This function will return the user object by email asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.email == email, self.model.deleted_at == deleted_at
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_bulk_emails(self, db: AsyncSession, emails: list):
        """This function will return the user objects by email asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.email.in_(emails))
            result = await db.execute(stmt)
            return result.scalars().all()

    async def find_by_username(self, db: AsyncSession, username: str):
        """This function will return the username object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.username == username)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_user_by_otp_reference(
        self, db: AsyncSession, otp_reference: int, user_id: int, driver_id: int
    ):
        """This function will return the username object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(
                self.model.otp_code == otp_reference,
                self.model.user_id == user_id,
                self.model.driver_id == driver_id,
                self.model.deleted_at == constant.STATUS_NULL,
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_verified_phone_user(self, db: AsyncSession, phone: str):
        """This function will return the username object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.phone == phone)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_user_email(self, db: AsyncSession, email: str, otp_code: int):
        """This function will return the user objects by user_ids asynchronously."""
        async with db:  # Ensure the session context
            stmt = (
                select(self.model)
                .where(
                    self.model.email == email,
                    self.model.otp_code == otp_code,
                    self.model.expires_at > datetime.now(),
                    self.model.deleted_at == constant.STATUS_NULL,
                )
                .order_by(self.model.expires_at.desc())
            )
            result = await db.execute(stmt)
            return result.scalars().all()

    async def create_or_find_device_token(
        self,
        db: AsyncSession,
        user_id: int,
        device_token: str,
        platform: str | None = None,
        device_id: str | None = None,
    ):
        """
        Create or update device token for a user.

        - If token already exists → return user
        - If token is different → update it
        """

        stmt = select(self.model).where(self.model.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        user.device_token = device_token  # create OR update
        user.platform = platform
        user.device_id = device_id

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    async def find_by_ride_id_status(self, db: AsyncSession, ride_id: int, ride_status):
        """This function is used to fetch the ride with status"""
        async with db:
            stmt = select(self.model).where(self.model.id == ride_id,
                                        self.model.status == ride_status)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_ride_by_user_id(
            self, db: AsyncSession, user_id: int, start_date: datetime, end_date: datetime
            ):
        """This methos is used to fetch the user rides data upto latest 5 days"""
        async with db:
            # Base filter
            date_filters = [
                self.model.user_id == user_id,
                self.model.deleted_at == constant.STATUS_NULL,
                self.model.created_at >= start_date,
                self.model.created_at <= end_date
            ]

            # Query 1: rides in date range
            stmt = (
                select(self.model)
                .where(*date_filters)
                .order_by(desc(self.model.created_at))
            )

            result = await db.execute(stmt)
            return result.scalars().all()

    async def find_ride_by_driver_id(
        self,
        db: AsyncSession,
        driver_id: int,
        start_date: datetime,
        end_date: datetime
    ):
        """Fetch rides within given date range (max 5 days)"""

        async with db:
            # Base filter
            date_filters = [
                self.model.driver_id == driver_id,
                self.model.deleted_at == constant.STATUS_NULL,
                self.model.created_at >= start_date,
                self.model.created_at <= end_date
            ]

            # Query 1: rides in date range
            stmt = (
                select(self.model)
                .where(*date_filters)
                .order_by(desc(self.model.created_at))
            )

            result = await db.execute(stmt)
            rides = result.scalars().all()

            total_filters = [
                self.model.driver_id == driver_id,
                self.model.deleted_at == constant.STATUS_NULL
            ]
            # Query 2: total count in same range
            count_stmt = (
                select(func.count())
                .select_from(self.model)
                .where(*total_filters)
            )

            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar_one()

            return {
                "rides": rides,
                "total_trips": total_count
            }

    async def find_drivers_list_with_pagination(self, db: AsyncSession, page, search_query):
        """This method is used the fetch the drivers list with search and pagination response."""
        page_limit = 5
        async with db:
            stmt = select(self.model)
            # Pagination calc
            offset = (page - 1) * page_limit

            # Search filter
            if search_query:
                stmt = stmt.where(self.model.full_name.ilike(f"%{search_query}%"))

            # Total count query
            count_stmt = select(func.count()).select_from(self.model)
            if search_query:
                count_stmt = count_stmt.where(self.model.full_name.ilike(f"%{search_query}%"))

            # Apply pagination
            stmt = stmt.offset(offset).limit(page_limit)

            # Execute queries
            result = await db.execute(stmt)
            drivers = result.scalars().all()

            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar_one()

            data = {
                "drivers": drivers,
                "total": total_count,
                "page": page,
                "limit": page_limit
            }
            return data
