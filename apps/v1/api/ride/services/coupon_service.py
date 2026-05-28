"""This module is used to implement coupon related functionality for rides."""

import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import timedelta
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
    constant.COUPON_KUBERSAVER: {
        "discount": 15.0,
        "description": "Flat ₹15 off on city and comfort rides",
    },
}


class CouponService(BaseResponseService):
    """This class is used to define the coupon related service methods."""

    async def get_loyalty_tier(self, db: AsyncSession, user_id: int) -> str:
        """
        Calculate and return user's loyalty tier based on total completed rides.
        Bronze: 0-10 rides
        Silver: 11-30 rides
        Gold: 31+ rides
        """
        stmt = select(func.count(Ride.id)).where(
            Ride.user_id == user_id,
            Ride.status == RideStatusEnum.COMPLETED.value,
            Ride.deleted_at == constant.STATUS_NULL,
        )
        result = await db.execute(stmt)
        total_rides = result.scalar() or 0

        if total_rides <= 10:
            return "Bronze"
        elif total_rides <= 30:
            return "Silver"
        else:
            return "Gold"

    async def get_reactivation_requirement(self, tier: str) -> int:
        """
        Get the number of rides without coupon needed to reactivate the coupon.
        """
        if tier == "Bronze":
            return 2
        elif tier == "Silver":
            return 1
        else:  # Gold
            return 0

    async def is_coupon_available(
        self,
        db: AsyncSession,
        user_id: int,
        coupon_code: str,
        ride_type: str,
    ) -> bool:
        """
        Check if the coupon_code is active/available for the user and ride_type.
        """
        coupon_code = coupon_code.upper().strip()
        if coupon_code != constant.COUPON_KUBERSAVER:
            # For backward compatibility, fallback to old checkers
            # TODO - eventually remove these and only use the new KUBERSAVER logic
            # if coupon_code == constant.COUPON_WELCOME50:
            #     return not await self._has_used_welcome(db, user_id)
            # elif coupon_code == constant.COUPON_COMMUTE25:
            #     return not await self._has_used_commute_today(db, user_id)
            return False

        if ride_type not in [constant.CITY_RIDE, constant.COMFORT_RIDE]:
            return False

        # 1. Find the most recent completed ride of this ride_type using this coupon
        stmt = (
            select(Ride)
            .where(
                Ride.user_id == user_id,
                Ride.coupon_code == constant.COUPON_KUBERSAVER,
                Ride.ride_type == ride_type,
                Ride.status == RideStatusEnum.COMPLETED.value,
                Ride.deleted_at == constant.STATUS_NULL,
            )
            .order_by(Ride.ride_date.desc())
        )

        result = await db.execute(stmt)
        last_coupon_ride = result.scalars().first()

        # If they've never completed a ride of this ride_type with KUBERSAVER, it is available (welcome gift)!
        if not last_coupon_ride:
            return True

        last_coupon_time = last_coupon_ride.ride_date
        last_coupon_date = last_coupon_time.date()
        today = datetime.now().date()

        # 2. Get loyalty tier and required rides for reactivation
        tier = await self.get_loyalty_tier(db, user_id)
        n_required = await self.get_reactivation_requirement(tier)

        # Gold tier always has coupon
        if n_required == 0:
            return True

        # 3. Check for streak resets (gap days)
        # Fetch all completed rides (any type) since last_coupon_date
        stmt_all = (
            select(Ride.ride_date)
            .where(
                Ride.user_id == user_id,
                Ride.status == RideStatusEnum.COMPLETED.value,
                Ride.deleted_at == constant.STATUS_NULL,
                func.date(Ride.ride_date) >= last_coupon_date,
            )
            .order_by(Ride.ride_date.asc())
        )

        result_all = await db.execute(stmt_all)
        completed_dates = {r.date() for r in result_all.scalars().all()}

        # Identify latest gap day strictly between last_coupon_date and today
        latest_gap_date = None
        current_date = last_coupon_date + timedelta(days=1)

        while current_date < today:
            if current_date not in completed_dates:
                latest_gap_date = current_date
            current_date += timedelta(days=1)

        # If a gap day was found, progress resets to the day after the gap
        if latest_gap_date:
            progress_start_date = latest_gap_date + timedelta(days=1)
        else:
            progress_start_date = last_coupon_date

        # 4. Count completed rides of this ride_type without a coupon since progress_start_date
        # (strictly after last_coupon_time)
        stmt_count = select(func.count(Ride.id)).where(
            Ride.user_id == user_id,
            Ride.ride_type == ride_type,
            Ride.status == RideStatusEnum.COMPLETED.value,
            Ride.deleted_at == constant.STATUS_NULL,
            (Ride.coupon_code == constant.STATUS_NULL)
            | (Ride.coupon_code == constant.EMPTY_STRING),
            Ride.ride_date > last_coupon_time,
            func.date(Ride.ride_date) >= progress_start_date,
        )

        result_count = await db.execute(stmt_count)
        rides_without_coupon = result_count.scalar() or 0

        return rides_without_coupon >= n_required

    async def validate_and_apply(
        self,
        db: AsyncSession,
        user_id: int,
        coupon_code: str,
        ride_type: str = None,
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
        # --- KUBERSAVER validation ---
        if coupon_code == constant.COUPON_KUBERSAVER:
            if not ride_type:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, "Ride type is required for this coupon"
                )

            is_valid = await self.is_coupon_available(
                db, user_id, coupon_code, ride_type
            )
            if not is_valid:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.couponAlreadyUsed
                )

        # --- WELCOME50 validation --- TODO - eventually remove this old logic once we are fully on the new KUBERSAVER system
        # elif coupon_code == constant.COUPON_WELCOME50:
        #     already_used = await self._has_used_welcome(db, user_id)
        #     if already_used:
        #         return self.response(
        #             status.HTTP_400_BAD_REQUEST, ErrorMessage.couponAlreadyUsed
        #         )

        # # --- COMMUTE25 validation ---
        # elif coupon_code == constant.COUPON_COMMUTE25:
        #     used_today = await self._has_used_commute_today(db, user_id)
        #     if used_today:
        #         return self.response(
        #             status.HTTP_400_BAD_REQUEST, ErrorMessage.couponAlreadyUsed
        #         )

        return self.response(
            status.HTTP_200_OK, InfoMessage.couponApplied, {"valid": True}
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

        user_obj = await UserAuthMethod(User).find_by_id(db, user_id)
        if not user_obj:
            return self.response(
                status.HTTP_401_UNAUTHORIZED, ErrorMessage.invalidUserOrNotFound
            )

        # KUBERSAVER availability check
        city_available = await self.is_coupon_available(
            db, user_id, constant.COUPON_KUBERSAVER, constant.CITY_RIDE
        )
        comfort_available = await self.is_coupon_available(
            db, user_id, constant.COUPON_KUBERSAVER, constant.COMFORT_RIDE
        )
        if city_available or comfort_available:
            desc = "Flat ₹15 off on Kuber Saver rides"
            if city_available and comfort_available:
                desc = "Flat ₹15 off — available on both city & comfort rides"
            elif city_available:
                desc = "Flat ₹15 off — available on city rides"
            elif comfort_available:
                desc = "Flat ₹15 off — available on comfort rides"

            available.append(
                {
                    "code": constant.COUPON_KUBERSAVER,
                    "is_city": city_available,
                    "is_comfort": comfort_available,
                    "discount": 15.0,
                    "description": desc,
                }
            )

        return self.response(status.HTTP_200_OK, InfoMessage.couponsFetched, available)

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
            Ride.status.in_(
                [
                    RideStatusEnum.COMPLETED.value,
                    RideStatusEnum.CANCELLED.value,
                ]
            ),
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
            Ride.status.in_(
                [
                    RideStatusEnum.COMPLETED.value,
                    RideStatusEnum.CANCELLED.value,
                ]
            ),
            func.date(Ride.created_at) == today,
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None
