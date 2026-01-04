"""This module is responsible for the creation of the driver plan service."""

from datetime import datetime, timedelta

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.driver.services.driver_firebase_notification import \
    DriverFirebaseNotification
from apps.v1.api.plans.models.method import PlansMethod
from apps.v1.api.plans.models.model import Plans
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from core.utils.message_variable import *

# Plan details: name -> {price, validity_days}
PLAN_DETAILS = {
    "Basic": {"price": 99, "validity": 30},
    "Premium": {"price": 199, "validity": 60},
    "Domestic": {"price": 299, "validity": 90},
    "International": {"price": 399, "validity": 150},  # 120+30
}

class DriverPlanService(BaseResponseService):
    """This class is used to define the driver plan service methods.
    """
    async def select_driver_plan(self, current_user, plan_name: str, db: AsyncSession):
        """
        Assigns a plan to a driver based on the selected plan name.
        Creates a new Plans record with the correct price and validity.
        """
        try:
            driver_id = current_user["user_id"]
            plan_info = PLAN_DETAILS.get(plan_name)
            if not plan_info:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidPlanName
                )

            # check if the driver already has a plan
            existing_plan = await PlansMethod(Plans).find_plan_by_driver_id(
                db, driver_id
            )
            if existing_plan:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.planAlreadyExists
                )

            price = plan_info["price"]
            validity = plan_info["validity"]
            start_date = datetime.now()
            expiry_date = start_date + timedelta(days=validity)

            new_plan = Plans(
                driver_id=driver_id,
                plan_name=plan_name,
                plan_days=validity,
                expiry_date=expiry_date,
                price=price,
                is_expired=constant.STATUS_FALSE,
            )

            if not await DataBaseMethod(Plans).save(new_plan, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
                )

            await db.commit()
            data = jsonable_encoder(new_plan)
            return self.response(
                status.HTTP_200_OK, InfoMessage.planSelectedSuccess, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def check_driver_plan_expiry_service(self, db: AsyncSession):
        """
        Checks the expiry status of all drivers' plans.
        Updates the plan status to expired if the current date exceeds the expiry date.
        """
        try:
            active_drivers = await PlansMethod(Plans).find_all_active_plans(db)
            current_date = datetime.now().date()
            expired_count = 0

            expired_plans = []
            for plan in active_drivers:
                if plan.expiry_date.date() <= current_date:
                    plan.is_expired = constant.STATUS_TRUE
                    expired_count += 1
                    expired_plans.append(plan)

            if expired_count > 0:
                driver_ids = [plan.driver_id for plan in expired_plans]
                drivers = await PlansMethod(Driver).find_plan_by_driver_id_list(db, driver_ids)
                print("Expired Drivers:", drivers)
                # Intialize the firebase notification service
                title = "Your plan has been expired"
                body = "Please select a new plan to continue using the service."
                await DriverFirebaseNotification().send_notification_to_drivers(drivers, title, body)
         
                return self.response(
                    status.HTTP_200_OK,
                    InfoMessage.plansChecked,
                    {"expired_count": expired_count},
                )
            else:
                return self.response(
                    status.HTTP_200_OK, InfoMessage.noPlansExpired, {"expired_count": expired_count}
                )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )