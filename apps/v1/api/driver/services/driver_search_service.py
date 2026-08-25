"""This module is finding driver using waves to fetch the response in given time"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

from apps.v1.api.driver.services.driver_firebase_notification import DriverFirebaseNotification
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from config.redis_config import redis_client
from core.redis_repo import RedisRideRepo, is_valid_device_token
from core.utils import constant_variable

LOG = logging.getLogger(__name__)

RIDE_SEARCH_TTL = 300  # 5 minutes total max lifetime of a ride search


class DriverSearchService:
    """Class for searching the driver in waves"""
    MAX_WAVES = 3
    WAVE_DELAY = 30
    WAVE_RADIUS = {1: 1, 2: 3, 3: 5}

    @staticmethod
    def serialize_user_data(user_data: Dict[str, Any]) -> Dict[str, str]:
        """This method serializes user data to ensure all values are
          strings for Firebase notification."""
        serialized = {}
        for key, value in (user_data or {}).items():
            try:
                if isinstance(value, (dict, list)):
                    serialized[key] = json.dumps(value)
                elif value is None:
                    serialized[key] = ""
                else:
                    serialized[key] = str(value)
            except Exception as e:
                LOG.error(f"Serialize error key={key}: {e}")
                serialized[key] = ""
        return serialized

    @staticmethod
    async def _fetch_eligible_drivers(
        ride_type: str,
        lng: float,
        lat: float,
        radius: float
    ) -> List[Dict[str, str]]:
        """
        Returns list of eligible drivers with their device tokens.
        A driver is eligible only if:
          1. Present in geo index within radius
          2. driver:alive key exists (heartbeat active = logged in)
          3. is_available == "1" in their meta
        """
        try:
            raw_drivers = await redis_client.georadius(
                f"drivers:geo:{ride_type}", lng, lat, radius, unit="km"
            )

            if not raw_drivers or not isinstance(raw_drivers, list):
                return []

            driver_ids = [str(d) for d in raw_drivers if d and str(d).strip()]
            if not driver_ids:
                return []

            LOG.info(f"Geo found {len(driver_ids)} drivers in {radius}km for {ride_type}")

            # --- Gate 1: Heartbeat check (logged in) ---
            async with redis_client.pipeline(transaction=False) as pipe:
                for driver_id in driver_ids:
                    pipe.exists(f"driver:alive:{driver_id}")
                alive_results = await pipe.execute()

            alive_ids = [
                did for did, alive in zip(driver_ids, alive_results) if alive
            ]
            LOG.info(f"Alive: {len(alive_ids)}/{len(driver_ids)}")

            if not alive_ids:
                return []

            # --- Gate 2: Not on an active ride ---
            async with redis_client.pipeline(transaction=False) as pipe:
                for driver_id in alive_ids:
                    pipe.exists(f"driver:busy:{driver_id}")
                busy_results = await pipe.execute()

            available_ids = [
                did for did, busy in zip(alive_ids, busy_results) if not busy
            ]
            LOG.info(f"Not busy: {len(available_ids)}/{len(alive_ids)}")

            if not available_ids:
                return []

            # --- Gate 3: Availability + device token ---
            async with redis_client.pipeline(transaction=False) as pipe:
                for driver_id in available_ids:
                    pipe.hmget(
                        f"driver:meta:{driver_id}",
                        "is_available", "device_token"
                    )
                meta_results = await pipe.execute()

            eligible = []
            for driver_id, meta in zip(available_ids, meta_results):
                is_available, device_token = meta[0], meta[1]

                if str(is_available or "0") != "1":
                    LOG.info(f"Driver {driver_id} not available, skip")
                    continue

                if not is_valid_device_token(device_token):
                    LOG.warning(f"Driver {driver_id} has no valid device token, skip")
                    continue

                eligible.append({
                    "driver_id": driver_id,
                    "device_token": str(device_token).strip()
                })

            LOG.info(
                f"Eligible: {len(eligible)}/{len(available_ids)} | "
                f"radius={radius}km | ride_type={ride_type}"
            )
            return eligible

        except Exception as e:
            LOG.error(f"_fetch_eligible_drivers error: {e}", exc_info=True)
            return []

    @staticmethod
    async def _send_notification_safe(
        driver_id: str,
        device_token: str,
        title: str,
        body: str,
        data: Dict[str, str]
    ) -> bool:
        try:
            sent = await DriverFirebaseNotification().send_notification_to_drivers(
                device_token, title, body, data
            )
            if sent:
                LOG.info(f"Notification sent → driver={driver_id}")
            else:
                LOG.warning(f"FCM rejected notification → driver={driver_id}")
            return sent
        except Exception as e:
            LOG.error(f"Notification failed → driver={driver_id}: {e}", exc_info=True)
            return False

    @staticmethod
    async def _emit_search_failed(ride_request_id: str, user_id: int):
        """Mark ride search as failed and notify the booking customer."""
        status = await RedisRideRepo.get_status(ride_request_id)
        if status != "-1":
            LOG.info(
                "Search failed skipped for ride=%s (status=%s)",
                ride_request_id,
                status,
            )
            return

        await RedisRideRepo.update_status(
            ride_request_id, RideStatusEnum.FAILED.value
        )
        await RideSocketEmitter.book_ride_status(
            ride_status=RideStatusEnum.FAILED.value,
            ride_request_id=ride_request_id,
            ride_id=ride_request_id,
            user_id=user_id,
        )
        LOG.info(
            "Emitted book_ride_status FAILED for ride=%s user=%s",
            ride_request_id,
            user_id,
        )

    @staticmethod
    async def _cleanup_ride(ride_request_id: str):
        """Set TTL on all ride search keys. Always awaited."""
        try:
            keys = [
                f"ride:search:{ride_request_id}",
                f"ride:wave:{ride_request_id}",
                f"ride:status:{ride_request_id}",
                f"ride:notified:{ride_request_id}",
                f"ride:candidates:{ride_request_id}",
            ]
            async with redis_client.pipeline(transaction=False) as pipe:
                for key in keys:
                    pipe.expire(key, 60)
                await pipe.execute()
            LOG.info(f"Cleanup TTL set for ride={ride_request_id}")
        except Exception as e:
            LOG.error(f"Cleanup error ride={ride_request_id}: {e}")

    @staticmethod
    async def start_wave(
        ride_request_id: str,
        ride_type: str,
        lat: float,
        lng: float,
        user_data: Dict[str, Any],
        user_id: int
    ):
        """Find drivers in waves and send notifications to nearby drivers."""
        if not all([ride_request_id, ride_type, lat is not None, lng is not None]):
            LOG.error("start_wave: missing required parameters")
            return

        # Serialize once before the loop
        serialized_payload = DriverSearchService.serialize_user_data(user_data)

        stats = {"found": 0, "sent": 0, "failed": 0, "skipped": 0}

        try:
            while True:
                # Always check status first before any work
                status = await RedisRideRepo.get_status(ride_request_id)
                if status != "-1":
                    LOG.info(
                        f"Ride {ride_request_id} status={status}, "
                        f"stopping search. stats={stats}"
                    )
                    return

                wave = await RedisRideRepo.get_wave(ride_request_id)
                LOG.info(
                    f"Starting wave {wave}/{DriverSearchService.MAX_WAVES} "
                    f"for ride={ride_request_id}"
                )

                # Max waves exceeded → mark failed
                if wave > DriverSearchService.MAX_WAVES:
                    LOG.warning(
                        f"Max waves reached for ride={ride_request_id}. stats={stats}"
                    )
                    await DriverSearchService._emit_search_failed(
                        ride_request_id, user_id
                    )
                    return

                radius = DriverSearchService.WAVE_RADIUS.get(wave, 5)

                # Fetch only truly eligible drivers (alive + available + has token)
                eligible_drivers = await DriverSearchService._fetch_eligible_drivers(
                    ride_type, lng, lat, radius
                )

                if not eligible_drivers:
                    LOG.info(
                        f"Wave {wave}: no eligible drivers in {radius}km. "
                        f"Moving to next wave in {DriverSearchService.WAVE_DELAY}s"
                    )
                    if wave >= DriverSearchService.MAX_WAVES:
                        await DriverSearchService._emit_search_failed(
                            ride_request_id, user_id
                        )
                        return
                    await RedisRideRepo.increment_wave(ride_request_id)
                    await asyncio.sleep(DriverSearchService.WAVE_DELAY)
                    continue

                stats["found"] += len(eligible_drivers)
                wave_sent = 0

                for driver in eligible_drivers:
                    driver_id = driver["driver_id"]
                    device_token = driver["device_token"]

                    # Gate 3: not already notified for this ride request
                    is_new = await RedisRideRepo.mark_driver_notified(
                        ride_request_id, driver_id
                    )
                    if not is_new:
                        LOG.debug(f"Driver {driver_id} already notified, skip")
                        stats["skipped"] += 1
                        continue

                    success = await DriverSearchService._send_notification_safe(
                        driver_id,
                        device_token,
                        constant_variable.RIDE_REQUEST_TITLE,
                        constant_variable.RIDE_REQUEST_BODY,
                        serialized_payload
                    )

                    if success:
                        stats["sent"] += 1
                        wave_sent += 1
                        await RedisRideRepo.add_candidates(ride_request_id, driver_id)
                    else:
                        stats["failed"] += 1

                LOG.info(
                    f"Wave {wave} complete | sent={wave_sent}/{len(eligible_drivers)} | "
                    f"stats={stats}"
                )

                await RedisRideRepo.increment_wave(ride_request_id)
                await asyncio.sleep(DriverSearchService.WAVE_DELAY)

        except asyncio.CancelledError:
            LOG.warning(f"start_wave cancelled for ride={ride_request_id}")
            await DriverSearchService._emit_search_failed(ride_request_id, user_id)

        except Exception as e:
            LOG.error(
                f"Critical error in start_wave ride={ride_request_id}: {e}",
                exc_info=True
            )
            await DriverSearchService._emit_search_failed(ride_request_id, user_id)

        finally:
            # Only expire search keys once dispatch has finished (accepted/failed/cancelled).
            status = await RedisRideRepo.get_status(ride_request_id)
            if status != "-1":
                await DriverSearchService._cleanup_ride(ride_request_id)
