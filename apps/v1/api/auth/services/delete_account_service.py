"""Service for soft-deleting customer and driver accounts."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import Session, User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.method import VehicleMethod
from apps.v1.api.vehicle.models.model import Vehicle
from core.utils import DateTimeUtils
from core.utils import constant_variable as constant
from core.utils.message_variable import ErrorMessage, InfoMessage


class DeleteAccountService(BaseResponseService):
    """Soft-deletes the authenticated customer or driver account."""

    async def delete_account_service(self, db: AsyncSession, current_user: dict):
        """
        Soft-delete the logged-in account, clear sessions, and (for drivers)
        go offline and soft-delete vehicles. Re-registration with the same
        email or mobile is blocked for ACCOUNT_DELETION_COOLING_DAYS.
        """
        try:
            user_type = current_user.get("user_type")
            if user_type not in (
                UserTypeEnum.CUSTOMER.value,
                UserTypeEnum.DRIVER.value,
            ):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidUserOrNotFound
                )

            model = Driver if user_type == UserTypeEnum.DRIVER.value else User
            result = await db.execute(
                select(model).where(
                    model.id == current_user.get("user_id"),
                    model.deleted_at == constant.STATUS_NULL,
                )
            )
            user_obj = result.scalars().first()
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )

            deleted_at = DateTimeUtils.get_time().replace(tzinfo=None)
            user_obj.deleted_at = deleted_at

            if user_type == UserTypeEnum.CUSTOMER.value:
                user_obj.code = constant.STATUS_NULL
                user_id, driver_id = user_obj.id, None
            else:
                user_obj.is_available = constant.STATUS_FALSE
                user_id, driver_id = None, user_obj.id
                vehicles = await VehicleMethod(Vehicle).find_all_by_driver_id(
                    db, user_obj.id
                )
                for vehicle in vehicles:
                    vehicle.deleted_at = deleted_at
                    db.add(vehicle)

            db.add(user_obj)

            sessions = await UserAuthMethod(Session).find_all_sessions_by_account(
                db, user_id=user_id, driver_id=driver_id
            )
            for session_obj in sessions:
                await db.delete(session_obj)

            await db.commit()
            return self.response(status.HTTP_200_OK, InfoMessage.accountDeleted)

        except Exception:
            await db.rollback()
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
