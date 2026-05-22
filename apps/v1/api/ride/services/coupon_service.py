"""This module is used to implement coupon related functionality for rides."""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.models.attribute import RideStatusEnum
from core.utils import constant_variable as constant
from apps.v1.api.base_service import BaseResponseService
from core.utils.message_variable import ErrorMessage, InfoMessage
from fastapi import status
from apps.v1.api.auth.models.model import User
from apps.v1.api.auth.models.method import UserAuthMethod

LOG = logging.getLogger(__name__)

COUPON_CONFIG = {
    constant.COUPON_WELCOME50: {
        "discount": 50.0,
        "description": "Welcome discount for first ride",
    },
    constant.COUPON_COMMUTE25: {
        "discount": 25.0,
        "description": "Daily commuter discount",
    },
}


class CouponService(BaseResponseService):
    """This class is used to define the coupon related service methods."""

    async def validate_and_apply(
        self,
        db: AsyncSession,
        user_id: int,
        coupon_code: str,
        ride_fare: float,
    ) -> dict:
        """
        Validate coupon and return discount details.
        Call this at booking time before creating the ride.

        Returns:
            {
                "valid": True/False,
                "discount_fare": float,
                "total_fare": float,
                "error": str or None
            }
        """
        coupon_code = coupon_code.upper().strip()

        # --- Unknown coupon ---
        if coupon_code not in COUPON_CONFIG:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidCouponCode
                )

        config = COUPON_CONFIG[coupon_code]

        # --- WELCOME50 validation ---
        if coupon_code == constant.COUPON_WELCOME50:
            already_used = await CouponService._has_used_welcome(self, db, user_id)
            if already_used:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.couponAlreadyUsed
                )

        # --- COMMUTE25 validation ---
        elif coupon_code == constant.COUPON_COMMUTE25:
            used_today = await CouponService._has_used_commute_today(self, db, user_id)
            if used_today:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.couponAlreadyUsed)

        discount = config["discount"]
        total_fare = max(0.0, ride_fare - discount)  # never go negative

        return self.response(
            status.HTTP_200_OK,
            InfoMessage.couponApplied,
            {
                "valid": True,
                "discount_fare": discount,
                "total_fare": total_fare,
                "error": None,
            }
        )

    async def get_available_coupons(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> list:
        """
        Returns coupons visible to the user on the booking screen.
        Call this when customer opens the booking screen.
        """
        available = []

        # WELCOME50 — only if never used
        user_obj = await UserAuthMethod(User).find_by_id(db, user_id)
        if not user_obj:
            return self.response(
                status.HTTP_401_UNAUTHORIZED, ErrorMessage.invalidUserOrNotFound
            )
        has_welcome = await CouponService._has_used_welcome(self, db, user_id)
        if not has_welcome:
            available.append({
                "code": constant.COUPON_WELCOME50,
                "discount": 50.0,
                "description": "50% off on your first ride",
            })

        # COMMUTE25 — only if not used today
        used_today = await CouponService._has_used_commute_today(self, db, user_id)
        if not used_today:
            available.append({
                "code": constant.COUPON_COMMUTE25,
                "discount": 25.0,
                "description": "Flat ₹25 off — once per day",
            })

        return self.response(
            status.HTTP_200_OK,
            InfoMessage.couponsFetched,
            available
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _has_used_welcome(self, db: AsyncSession, user_id: int) -> bool:
        """
        Returns True if user has ANY ride with WELCOME50 coupon
        that was completed OR cancelled after driver accepted.
        """
        stmt = select(Ride).where(
            Ride.user_id == user_id,
            Ride.coupon_code == constant.COUPON_WELCOME50,
            Ride.is_welcome == constant.STATUS_TRUE,
            Ride.deleted_at == constant.STATUS_NULL,
            Ride.status.in_([
                RideStatusEnum.COMPLETED.value,
                RideStatusEnum.CANCELLED.value,
            ])
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None

    async def _has_used_commute_today(self, db: AsyncSession, user_id: int) -> bool:
        """
        Returns True if user already used COMMUTE25 today
        on a completed or cancelled (post-accept) ride.
        """
        today = datetime.now().date()
        stmt = select(Ride).where(
            Ride.user_id == user_id,
            Ride.coupon_code == constant.COUPON_COMMUTE25,
            Ride.is_commuter == constant.STATUS_TRUE,
            Ride.deleted_at == constant.STATUS_NULL,
            Ride.status.in_([
                RideStatusEnum.COMPLETED.value,
                RideStatusEnum.CANCELLED.value,
            ]),
            func.date(Ride.created_at) == today,
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None
