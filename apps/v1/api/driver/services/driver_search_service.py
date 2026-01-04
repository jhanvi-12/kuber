"""This module is finding driver using waves to fetch the response in given time"""

import asyncio

from apps.v1.api.driver.services.driver_firebase_notification import (
    DriverFirebaseNotification,
)
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from config.redis_config import redis_client
from core.redis_repo import RedisRideRepo
from core.utils import constant_variable


class DriverSearchService:
    """Class for searching the driver in waves"""

    MAX_WAVES = 3
    WAVE_DELAY = 7  # seconds

    @staticmethod
    async def start_wave(ride_id, ride_type, lat, lng):
        """This method is used to find the drivers in waves from redis
        and send the notification to nearby drivers."""
        while True:
            wave = RedisRideRepo.get_wave(ride_id)
            print("*********", wave)

            # 🚫 Stop if ride already accepted / cancelled
            status = RedisRideRepo.get_status(ride_id)
            if status != "SEARCHING":
                return

            if wave > DriverSearchService.MAX_WAVES:
                RedisRideRepo.update_status(ride_id, "FAILED")
                await RideSocketEmitter.no_driver_found(ride_id)
                return

            drivers = redis_client.georadius(
                f"drivers:geo:{ride_type}", lng, lat, wave, unit="km", count=5
            )

            if not drivers:
                RedisRideRepo.update_status(ride_id, "FAILED")
                await RideSocketEmitter.no_driver_found(ride_id)
                return

            # FILTER: only drivers who were NOT notified
            new_drivers = [
                d
                for d in drivers
                if not RedisRideRepo.has_driver_been_notified(ride_id, d)
            ]
            if not new_drivers:
                await asyncio.sleep(DriverSearchService.WAVE_DELAY)
                RedisRideRepo.increment_wave(ride_id)
                continue

            pipe = redis_client.pipeline()

            RedisRideRepo.add_candidates(ride_id, drivers)
            for driver_id in drivers:
                pipe.hgetall(f"driver:meta:{driver_id}")
            driver_meta_list = pipe.execute()

            print("Drivers list :", driver_meta_list)
            for driver_id, meta in zip(drivers, driver_meta_list):
                device_token = meta.get("device_token")
                if not device_token:
                    continue
                await DriverFirebaseNotification().send_notification_to_drivers(
                    device_token,
                    constant_variable.RIDE_REQUEST_TITLE,
                    constant_variable.RIDE_REQUEST_BODY,
                )
                # ✅ MARK AS NOTIFIED (REUSE SAME SET)
                RedisRideRepo.add_candidates(ride_id, [driver_id])

            # ⏳ Wait before next wave
            await asyncio.sleep(DriverSearchService.WAVE_DELAY)
            RedisRideRepo.increment_wave(ride_id)
