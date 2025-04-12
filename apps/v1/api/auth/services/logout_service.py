"""This module contains logout functionality."""

from datetime import datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import Session
from apps.v1.api.base_service import BaseResponseService
from core.utils import message_variable


class UserLogoutService(BaseResponseService):
    """Service class for retrieving user details."""

    async def get_logout_service(self, db: AsyncSession, user_id: int, session_id: str):
        """This method is called when the user is logged out.

        Args:
            db (AsyncSession): Database connection
            user_id (int): User ID.
        Returns:
            StandardResponse: A response object with status and message.
        """
        session_obj = await UserAuthMethod(Session).find_by_session_id(
            db, user_id, session_id
        )
        if not session_obj:
            return self.response(
                status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid session ID"
            )

        session_obj.expires_at = datetime.utcnow()
        db.add(session_obj)
        await db.commit()

        return self.response(
            status_code=status.HTTP_200_OK, message=message_variable.LOGOUT_SUCCESSFULLY
        )
