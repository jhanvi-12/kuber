"""This module is finding driver using waves to fetch the response in given time"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

from apps.v1.api.driver.services.driver_firebase_notification import \
    DriverFirebaseNotification
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from config.redis_config import redis_client
from core.redis_repo import RedisRideRepo
from core.utils import constant_variable

LOG = logging.getLogger(__name__)

class DriverSearchService:
    """Class for searching the driver in waves"""

    MAX_WAVES = 3
    WAVE_DELAY = 30  # seconds
    MIN_DRIVERS_PER_WAVE = 1  # Minimum drivers to consider wave successful

    WAVE_RADIUS = {
        1: 1,   # 0–1 km
        2: 3,   # 1–3 km
        3: 5,   # 3–5 km
    }

    @staticmethod
    def _serialize_user_data(user_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Convert all user_data values to strings for FCM compatibility.
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            Dictionary with all values converted to strings
        """
        if not user_data:
            return {}
            
        serialized = {}
        for key, value in user_data.items():
            try:
                if isinstance(value, (dict, list)):
                    # Convert complex objects to JSON strings
                    serialized[key] = json.dumps(value)
                elif value is None:
                    serialized[key] = ""
                else:
                    # Convert all other types to string
                    serialized[key] = str(value)
            except Exception as e:
                LOG.error(f"Error serializing key {key}: {str(e)}")
                serialized[key] = ""
        
        LOG.debug(f"Serialized user data: {serialized}")
        return serialized

    @staticmethod
    async def _validate_driver_meta(
        driver_id: str,
        meta: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Validate driver metadata and extract device token.
        
        Args:
            driver_id: Driver's unique identifier
            meta: Driver metadata from Redis
            
        Returns:
            Device token if valid, None otherwise
        """
        if not meta:
            LOG.warning(f"Driver {driver_id} has no metadata in Redis")
            return None
        
        if not isinstance(meta, dict):
            LOG.warning(f"Driver {driver_id} metadata is not a dictionary: {type(meta)}")
            return None
        
        device_token = meta.get("device_token")
        
        if not device_token:
            LOG.warning(f"Driver {driver_id} has no device_token")
            return None
        
        if not isinstance(device_token, str) or len(device_token) < 10:
            LOG.warning(f"Driver {driver_id} has invalid device_token format")
            return None
        
        return device_token

    @staticmethod
    async def _send_notification_safe(
        driver_id: str,
        device_token: str,
        title: str,
        body: str,
        data: Dict[str, str]
    ) -> bool:
        """
        Safely send notification with error handling.
        
        Args:
            driver_id: Driver's unique identifier
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Notification data payload (must be string values)
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            await DriverFirebaseNotification().send_notification_to_drivers(
                device_token,
                title,
                body,
                data
            )
            LOG.info(f" Notification sent successfully to driver {driver_id}")
            return True

        except Exception as e:
            LOG.error(
                f" Failed to send notification to driver {driver_id}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    async def _fetch_drivers_in_radius(
        ride_type: str,
        lng: float,
        lat: float,
        radius: float
    ) -> List[str]:
        """
        Fetch drivers within specified radius.
        
        Args:
            ride_type: Type of ride (e.g., 'standard', 'premium')
            lng: Longitude
            lat: Latitude
            radius: Search radius in km
            
        Returns:
            List of driver IDs
        """
        try:
            drivers = await redis_client.georadius(
                f"drivers:geo:{ride_type}",
                lng,
                lat,
                radius,
                unit="km"
            )
            
            # Ensure drivers is a list
            if not isinstance(drivers, list):
                LOG.warning(f"georadius returned non-list: {type(drivers)}")
                return []
            
            # Filter out None, empty strings, or invalid entries
            valid_drivers = [
                str(d) for d in drivers 
                if d is not None and str(d).strip()
            ]

            LOG.info(
                f"Found {len(valid_drivers)} drivers in {radius}km radius "
                f"for ride_type '{ride_type}'"
            )

            return valid_drivers

        except Exception as e:
            LOG.error(f"Error fetching drivers from Redis: {str(e)}", exc_info=True)
            return []

    @staticmethod
    async def start_wave(
        ride_request_id: str,
        ride_type: str,
        lat: float,
        lng: float,
        user_data: Dict[str, Any]
    ):
        """
        Find drivers in waves and send notifications to nearby drivers.
        
        Args:
            ride_request_id: Unique ride request identifier
            ride_type: Type of ride
            lat: Pickup latitude
            lng: Pickup longitude
            user_data: User information to send to drivers
        """
        # Validate inputs
        if not all([ride_request_id, ride_type, lat, lng]):
            LOG.error("Missing required parameters for driver search")
            return

        # Serialize user data once BEFORE the loop
        serialized_user_data = DriverSearchService._serialize_user_data(user_data)

        notification_stats = {
            'total_drivers_found': 0,
            'total_notifications_sent': 0,
            'total_notifications_failed': 0
        }

        try:
            while True:
                # Get current wave
                wave = await RedisRideRepo.get_wave(ride_request_id)

                # Check ride status FIRST
                status = await RedisRideRepo.get_status(ride_request_id)
                if status != "Searching":
                    LOG.info(
                        f"Ride {ride_request_id} status changed to '{status}'. "
                        f"Stopping search. Stats: {notification_stats}"
                    )
                    return

                LOG.info(f"Wave {wave}/{DriverSearchService.MAX_WAVES} for ride {ride_request_id}")

                # Check if max waves reached BEFORE fetching drivers
                if wave > DriverSearchService.MAX_WAVES:
                    LOG.warning(
                        f"Max waves ({DriverSearchService.MAX_WAVES}) reached "
                        f"for ride {ride_request_id}. Stats: {notification_stats}"
                    )

                    # Double-check status before failing
                    status = await RedisRideRepo.get_status(ride_request_id)
                    if status == "Searching":
                        await RedisRideRepo.update_status(
                            ride_request_id,
                            RideStatusEnum.FAILED.value
                        )
                        await RideSocketEmitter.book_ride_status(
                            RideStatusEnum.FAILED.value,
                            ride_request_id
                        )
                    return  # EXIT - Don't continue the loop

                # Get radius for current wave
                radius = DriverSearchService.WAVE_RADIUS.get(wave, 5)

                # Fetch drivers in radius
                drivers = await DriverSearchService._fetch_drivers_in_radius(
                    ride_type, lng, lat, radius
                )

                # If no drivers found, move to next wave WITHOUT sending notifications
                if not drivers or len(drivers) == 0:
                    LOG.info(
                        f" No drivers found in {radius}km radius for wave {wave}. "
                        f"Moving to next wave in {DriverSearchService.WAVE_DELAY}s"
                    )
                    await RedisRideRepo.increment_wave(ride_request_id)
                    await asyncio.sleep(DriverSearchService.WAVE_DELAY)
                    continue  # SKIP to next iteration - NO NOTIFICATION SENT

                # ONLY reach here if drivers were found
                notification_stats['total_drivers_found'] += len(drivers)
                LOG.info(f" Found {len(drivers)} drivers in wave {wave}: {drivers}")

                # Fetch driver metadata in batch
                pipe = redis_client.pipeline()
                for driver_id in drivers:
                    await pipe.hgetall(f"driver:meta:{driver_id}")

                driver_meta_list = await pipe.execute()

                # Process each driver - ONLY if we have drivers
                notified_count = 0
                for driver_id, meta in zip(drivers, driver_meta_list):
                    # Check if driver already notified
                    is_new = await RedisRideRepo.mark_driver_notified(
                        ride_request_id, driver_id
                    )

                    if not is_new:
                        LOG.debug(f"Driver {driver_id} already notified, skipping")
                        continue

                    # Validate driver metadata and get device token
                    device_token = await DriverSearchService._validate_driver_meta(
                        driver_id, meta
                    )

                    if not device_token:
                        LOG.warning(f"Driver {driver_id} has no valid device token")
                        notification_stats['total_notifications_failed'] += 1
                        continue  # Skip this driver

                    # ONLY SEND NOTIFICATION IF WE HAVE A VALID TOKEN
                    LOG.info(f"Sending notification to driver {driver_id}")
                    success = await DriverSearchService._send_notification_safe(
                        driver_id,
                        device_token,
                        constant_variable.RIDE_REQUEST_TITLE,
                        constant_variable.RIDE_REQUEST_BODY,
                        serialized_user_data  # Already serialized
                    )

                    if success:
                        notification_stats['total_notifications_sent'] += 1
                        notified_count += 1
                        # Mark as candidate
                        await RedisRideRepo.add_candidates(ride_request_id, [driver_id])
                    else:
                        notification_stats['total_notifications_failed'] += 1

                LOG.info(
                    f"Wave {wave} complete: Notified {notified_count}/{len(drivers)} drivers. "
                    f"Overall stats: {notification_stats}"
                )

                # Move to next wave
                await RedisRideRepo.increment_wave(ride_request_id)
                await asyncio.sleep(DriverSearchService.WAVE_DELAY)

        except asyncio.CancelledError:
            LOG.info(f"Driver search cancelled for ride {ride_request_id}")
            raise
        except Exception as e:
            LOG.error(
                f"Critical error in driver search for ride {ride_request_id}: {str(e)}",
                exc_info=True
            )
            # Mark ride as failed
            try:
                await RedisRideRepo.update_status(
                    ride_request_id,
                    RideStatusEnum.FAILED.value
                )
                await RideSocketEmitter.book_ride_status(
                    RideStatusEnum.FAILED.value,
                    ride_request_id
                )
                # Expire the Redis key to clean up state
                redis_client.expire(f"ride:search:{ride_request_id}", 2)
            except Exception as cleanup_error:
                LOG.error(f"Error during cleanup: {str(cleanup_error)}")


# """This module is finding driver using waves to fetch the response in given time"""

# import asyncio
# import logging

# from apps.v1.api.driver.services.driver_firebase_notification import \
#     DriverFirebaseNotification
# from apps.v1.api.ride.models.attribute import RideStatusEnum
# from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
# from config.redis_config import redis_client
# from core.redis_repo import RedisRideRepo
# from core.utils import constant_variable

# LOG = logging.getLogger(__name__)

# class DriverSearchService:
#     """Class for searching the driver in waves"""

#     MAX_WAVES = 3
#     WAVE_DELAY = 30  # seconds

#     WAVE_RADIUS = {
#         1: 1,   # 0–1 km
#         2: 3,   # 1–3 km
#         3: 5,   # 3–5 km
#     }

#     @staticmethod
#     async def start_wave(ride_request_id, ride_type, lat, lng, user_data):
#         """This method is used to find the drivers in waves from redis
#         and send the notification to nearby drivers."""
#         while True:
#             wave = await RedisRideRepo.get_wave(ride_request_id)
#             LOG.info(wave)

#             # Stop if ride already accepted / cancelled
#             status = await RedisRideRepo.get_status(ride_request_id)
#             if status != "Searching":
#                 return

#             LOG.info(f"Current wave: {wave}")
#             if wave > DriverSearchService.MAX_WAVES:
#                 LOG.info("Waves are completed")
#                 # Double-check status before failing (avoid race condition)
#                 status = await RedisRideRepo.get_status(ride_request_id)
#                 if status == "Searching":
#                     await RedisRideRepo.update_status(
#                         ride_request_id,
#                         RideStatusEnum.FAILED.value
#                     )

#                     await RideSocketEmitter.book_ride_status(
#                         RideStatusEnum.FAILED.value,
#                         ride_request_id
#                     )
#                     return
#             radius = DriverSearchService.WAVE_RADIUS[wave]
#             drivers = await redis_client.georadius(
#                 f"drivers:geo:{ride_type}", lng, lat, radius, unit="km"
#             )
#             LOG.info(drivers)
#             if not drivers:
#                 await asyncio.sleep(DriverSearchService.WAVE_DELAY)
#                 await RedisRideRepo.increment_wave(ride_request_id)
#                 continue

#             pipe = redis_client.pipeline()

#             for driver_id in drivers:
#                 await pipe.hgetall(f"driver:meta:{driver_id}")
#             driver_meta_list = await pipe.execute()

#             for driver_id, meta in zip(drivers, driver_meta_list):
#                 is_new = await RedisRideRepo.mark_driver_notified(
#                     ride_request_id, driver_id
#                 )

#                 if not is_new:
#                     continue

#                 device_token = meta.get("device_token")
#                 if not device_token:
#                     continue
#                 await DriverFirebaseNotification().send_notification_to_drivers(
#                     device_token,
#                     constant_variable.RIDE_REQUEST_TITLE,
#                     constant_variable.RIDE_REQUEST_BODY,
#                     user_data

#                 )
#                 # MARK AS NOTIFIED (REUSE SAME SET)
#                 await RedisRideRepo.add_candidates(ride_request_id, [driver_id])

#             # Wait before next wave
#             await RedisRideRepo.increment_wave(ride_request_id)
#             await asyncio.sleep(DriverSearchService.WAVE_DELAY)
