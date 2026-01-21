"""This module is finding driver using waves to fetch the response in given time"""

import asyncio

from apps.v1.api.driver.services.driver_firebase_notification import \
    DriverFirebaseNotification
from apps.v1.api.ride.models.attribute import RideStatusEnum
from config.redis_config import redis_client
from core.redis_repo import RedisRideRepo
from core.utils import constant_variable


class DriverSearchService:
    """Class for searching the driver in waves"""

    MAX_WAVES = 3
    WAVE_DELAY = 7  # seconds

    WAVE_RADIUS = {
        1: 1,   # 0–1 km
        2: 3,   # 1–3 km
        3: 5,   # 3–5 km
    }

    @staticmethod
    async def start_wave(ride_id, ride_type, lat, lng):
        """This method is used to find the drivers in waves from redis
        and send the notification to nearby drivers."""
        while True:
            wave = await RedisRideRepo.get_wave(ride_id)
            print("*********", wave)

            # Stop if ride already accepted / cancelled
            status = await RedisRideRepo.get_status(ride_id)
            if status != RideStatusEnum.SEARCHING.value:
                return

            if wave > DriverSearchService.MAX_WAVES:
                print("Waves are completed")
                return

            radius = DriverSearchService.WAVE_RADIUS[wave]

            drivers = await redis_client.georadius(
                f"drivers:geo:{ride_type}", lng, lat, radius, unit="km"
            )

            if not drivers:
                await asyncio.sleep(DriverSearchService.WAVE_DELAY)
                await RedisRideRepo.increment_wave(ride_id)
                continue

            pipe = await redis_client.pipeline()

            for driver_id in drivers:
                await pipe.hgetall(f"driver:meta:{driver_id}")
            driver_meta_list = await pipe.execute()

            for driver_id, meta in zip(drivers, driver_meta_list):
                is_new = await RedisRideRepo.mark_driver_notified(
                    ride_id, driver_id
                )

                if not is_new:
                    continue

                device_token = meta.get("device_token")
                if not device_token:
                    continue
                await DriverFirebaseNotification().send_notification_to_drivers(
                    device_token,
                    constant_variable.RIDE_REQUEST_TITLE,
                    constant_variable.RIDE_REQUEST_BODY,
                )
                # MARK AS NOTIFIED (REUSE SAME SET)
                await RedisRideRepo.add_candidates(ride_id, [driver_id])

            # Wait before next wave
            await RedisRideRepo.increment_wave(ride_id)
            await asyncio.sleep(DriverSearchService.WAVE_DELAY)
