"""Scheduler for checking driver plan expiration and sending notifications."""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.v1.api.driver.models.model import Driver
from apps.v1.api.plans.models.model import Plans
# from core.utils.notification_service import send_push_notification  # Assume this exists or stub below

# Stub for push notification (replace with actual implementation)
async def send_push_notification(device_token: str, title: str, message: str):
    # Implement actual push notification logic here
    print(f"Sending notification to {device_token}: {title} - {message}")


async def check_and_notify_expired_plans(db: AsyncSession):
    now = datetime.now()
    # Get all active, non-expired plans that have expired
    result = await db.execute(
        select(Plans).where(
            Plans.is_expired == False,
            Plans.expiry_date <= now
        )
    )
    expired_plans = result.scalars().all()
    for plan in expired_plans:
        # Mark plan as expired
        plan.is_expired = True
        # Get driver info
        driver_result = await db.execute(select(Driver).where(Driver.id == plan.driver_id))
        driver = driver_result.scalar_one_or_none()
        if driver and driver.device_token:
            await send_push_notification(
                driver.device_token,
                title="Plan Expired",
                message=f"Your {plan.plan_name} has expired. Please renew to continue enjoying our services."
            )
    await db.commit()


def start_plan_expiry_scheduler(db: AsyncSession):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_notify_expired_plans,
        'cron',
        hour=0, minute=0,  # Midnight
        args=[db],
        id='plan_expiry_check',
        replace_existing=True
    )
    scheduler.start() 