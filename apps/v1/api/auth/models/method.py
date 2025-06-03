"""This module contains database operations methods."""

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.utils import constant_variable as constant

class UserAuthMethod:
    """This class defines methods to authenticate users."""

    def __init__(self, model) -> None:
        self.model = model

    async def find_by_id(self, db: AsyncSession, user_id: int, deleted_at = constant.STATUS_NULL):
        """This function will returns the user object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.id == user_id,
                                            self.model.deleted_at == deleted_at)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_session_id(self, db: AsyncSession, user_id: int, session_id: str):
        """This function will return the user session object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.user_id == user_id,
                                            self.model.session_id == session_id)
        
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_email(self, db: AsyncSession, email: str, deleted_at = constant.STATUS_NULL):
        """This function will return the user object by email asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.email == email,
                                            self.model.deleted_at == deleted_at)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_verified_email_user(self, db: AsyncSession, email: str, deleted_at = constant.STATUS_NULL):
        """This function will return the user object by email asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.email == email,
                                            self.model.deleted_at == deleted_at,
                                            self.model.is_verified == constant.STATUS_TRUE)
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
                self.model.deleted_at == constant.STATUS_NULL
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_verified_phone_user(self, db: AsyncSession, phone: str):
        """This function will return the username object"""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.phone == phone)
            result = await db.execute(stmt)
            return result.scalars().first()

    async def find_by_license_ids(self, db: AsyncSession, license_ids: list):
        """This function will return the user objects by user_ids asynchronously."""
        async with db:  # Ensure the session context
            stmt = select(self.model).where(self.model.license_id.in_(license_ids))
            result = await db.execute(stmt)
            return result.scalars().all()

