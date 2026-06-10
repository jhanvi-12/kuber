"""This module is used to work with redis and there functionality"""

import time

from apps.v1.api.ride.models.attribute import RideStatusEnum
from config.redis_config import redis_client
import logging
from core.utils import constant_variable

DRIVER_ALIVE_TTL = 120       # 2 min — renewed by heartbeat
DRIVER_META_TTL = 1800       # half an hour — auto cleanup if driver never logs out cleanly
DRIVER_GEO_TTL = 1800        # half an hour — same
# FCM registration tokens are JWT-length strings (typically 140+ chars).
MIN_DEVICE_TOKEN_LENGTH = 80
INVALID_DEVICE_TOKEN_VALUES = frozenset({"", "none", "null", "undefined"})

LOG = logging.getLogger(__name__)


def is_valid_device_token(device_token) -> bool:
    """Return True for a non-empty FCM token; reject placeholders like 'None'."""
    if device_token is None:
        return False
    token = str(device_token).strip()
    if token.lower() in INVALID_DEVICE_TOKEN_VALUES:
        return False
    return len(token) >= MIN_DEVICE_TOKEN_LENGTH

class RedisRideRepo:
    """This class is used to represenst all ride methods to store data in redis."""

    @classmethod
    async def init_search_state(cls, ride_request_id: str, user_id: int, payload: dict):
        """Initiate the driver search."""
        key = f"ride:search:{ride_request_id}"

        data = {
            "status": "-1", # Searching
            "user_id": user_id,
            "pickup_latitude": payload["pickup_latitude"],
            "pickup_longitude": payload["pickup_longitude"],
            "pickup_address": payload["pickup_address"],
            "destination_latitude": payload["destination_latitude"],
            "destination_longitude": payload["destination_longitude"],
            "destination_address": payload["destination_address"],
            "ride_type": payload["ride_type"],
            "ride_fare": payload["ride_fare"],
            "discount_fare": payload["discount_fare"],
            "total_fare": payload["total_fare"],
            "distance": payload["distance"],
            "duration": payload["duration"],
            "coupon_code": payload.get("coupon_code", None),
            "wave": 1,
            "created_at": int(time.time()),
        }

        async with redis_client.pipeline() as pipe:
            # Store ride request
            await pipe.hmset(key, mapping=data)

            # Safety TTL (auto cleanup after 10 minutes)
            await pipe.expire(key, 600)

            # Cleanup related keys (if any)
            await pipe.delete(f"ride:lock:{ride_request_id}")
            await pipe.delete(f"ride:candidates:{ride_request_id}")
            await pipe.delete(f"ride:notified:{ride_request_id}")

            await pipe.execute()

    @classmethod
    async def acquire_lock(cls, ride_request_id: str, driver_id: int) -> bool:
        """
        Prevents multiple drivers from accepting the same ride.
        Uses atomic SETNX operation.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            driver_id: ID of the driver attempting to accept
            
        Returns:
            bool: True if lock acquired, False if already locked
        """
        lock_key = f"ride:lock:{ride_request_id}"

        # SETNX: Set if not exists (atomic operation)
        is_locked = await redis_client.set(
            lock_key,
            str(driver_id),
            nx=True,  # Only set if not exists
            ex=600    # Expire in 10 minutes
        )

        return is_locked is not None

    @classmethod
    async def release_lock(cls, ride_request_id: str):
        """
        Release the lock on a ride request.
        
        Args:
            ride_request_id: Unique identifier for the ride request
        """
        lock_key = f"ride:lock:{ride_request_id}"
        await redis_client.delete(lock_key)

    @classmethod
    async def update_status(cls, ride_request_id: str, status: str):
        """
        Update the status of a ride request.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            status: New status (e.g., 'SEARCHING', 'ACCEPTED', 'CANCELLED')
        """
        key = f"ride:search:{ride_request_id}"
        await redis_client.hset(key, "status", status)

    @classmethod
    async def get_status(cls, ride_request_id: str) -> str:
        """
        Get the current status of a ride request.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            
        Returns:
            str: Current status or None if not found
        """
        key = f"ride:search:{ride_request_id}"
        status = await redis_client.hget(key, "status")
        return status

    @classmethod
    async def get_wave(cls, ride_request_id: str) -> int:
        """
        Get the current search wave number.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            
        Returns:
            int: Current wave number (defaults to 1)
        """
        key = f"ride:search:{ride_request_id}"
        wave = await redis_client.hget(key, "wave")
        return int(wave) if wave else 1

    @classmethod
    async def increment_wave(cls, ride_request_id: str) -> int:
        """
        Increment the search wave number.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            
        Returns:
            int: New wave number
        """
        key = f"ride:search:{ride_request_id}"
        new_wave = await redis_client.hincrby(key, "wave", 1)
        return new_wave

    @classmethod
    async def get_ride_data(cls, ride_request_id: str) -> dict:
        """
        Get all ride request data from Redis.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            
        Returns:
            dict: All ride data or empty dict if not found
        """
        key = f"ride:search:{ride_request_id}"
        data = await redis_client.hgetall(key)
        return data if data else {}

    @classmethod
    async def delete_ride_data(cls, ride_request_id: str):
        """
        Delete all ride request data and related keys.
        
        Args:
            ride_request_id: Unique identifier for the ride request
        """
        keys = [
            f"ride:search:{ride_request_id}",
            f"ride:lock:{ride_request_id}",
            f"ride:candidates:{ride_request_id}"
        ]
        await redis_client.delete(*keys)

    @classmethod
    async def add_candidates(cls, ride_request_id: str, driver_id: int):
        """
        Add a driver to the list of candidates who were notified.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            driver_id: ID of the driver to add
        """
        key = f"ride:candidates:{ride_request_id}"
        await redis_client.sadd(key, str(driver_id))
        await redis_client.expire(key, 600)  # 10 minutes TTL

    @classmethod
    async def get_candidate_drivers(cls, ride_request_id: str) -> set:
        """
        Get all candidate drivers who were notified.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            
        Returns:
            set: Set of driver IDs
        """
        key = f"ride:candidates:{ride_request_id}"
        candidates = await redis_client.smembers(key)
        return {int(d) for d in candidates} if candidates else set()

    @classmethod
    async def has_driver_been_notified(cls, ride_request_id: str, driver_id: int) -> bool:
        """
        Check if a driver was already notified about this ride.
        
        Args:
            ride_request_id: Unique identifier for the ride request
            driver_id: ID of the driver to check
            
        Returns:
            bool: True if driver was already notified
        """
        key = f"ride:candidates:{ride_request_id}"
        return await redis_client.sismember(key, str(driver_id))

    @staticmethod
    async def mark_driver_notified(ride_id: str, driver_id: str) -> bool:
        """
        Atomically marks driver as notified for this ride search.
        Returns True only if driver was NOT notified before (SADD added 1 member).
        """
        added = await redis_client.sadd(
            f"ride:notified:{ride_id}",
            str(driver_id),
        )
        await redis_client.expire(f"ride:notified:{ride_id}", 600)
        return added == 1

    @classmethod
    async def get_assigned_driver(cls, ride_request_id: str):
        """
        Returns the driver_id who has locked/accepted the ride.
        Returns None if no driver is assigned.
        """
        key = f"ride:lock:{ride_request_id}"

        driver_id = await redis_client.get(key)
        if not driver_id:
            return None

        # Redis returns bytes → convert to int
        return int(driver_id)

    @classmethod
    async def mark_accepted(cls, ride_request_id: str, driver_id: int):
        """
        Returns False if ride already accepted
        """
        if not cls.acquire_lock(ride_request_id, driver_id):
            return False

        await redis_client.hmset(
            f"ride:search:{ride_request_id}",
            mapping={
                "status": RideStatusEnum.ACCEPTED.value,
                "driver_id": driver_id,
                "accepted_at": int(time.time())
            }
        )
        return True

    @classmethod
    async def mark_rejected(cls, ride_request_id, driver_id):
        """This method is used when ride is rejected by driver"""
        await redis_client.sadd(f"ride:rejected:{ride_request_id}", driver_id)
        await redis_client.expire(f"ride:rejected:{ride_request_id}", 300)

    @classmethod
    async def get_db_ride_id(cls, ride_request_id: str) -> int | None:
        """This method is used to get the ride ID"""
        key = f"ride:search:{ride_request_id}"
        ride_id = await redis_client.hget(key, "ride_id")
        return int(ride_id) if ride_id else None


class RedisDriverRepo:
    """This class is used to store the drivers related details"""

    @staticmethod
    def _geo_key(ride_type: str):
        return f"drivers:geo:{ride_type}"

    @staticmethod
    def _meta_key(driver_id: int) -> str:
        return f"driver:meta:{driver_id}"

    @staticmethod
    def _alive_key(driver_id: int) -> str:
        return f"driver:alive:{driver_id}"

    @classmethod
    async def update_driver_status(
        cls,
        driver_id: int,
        ride_type: str,
        is_available: bool,
        lat: float = None,
        lng: float = None,
        device_token: str = None,
    ):
        """
        Online  → geo add + meta set + alive key with TTL
        Offline → geo remove + mark unavailable + delete alive key
        All via pipeline (single round trip).
        """
        try:
            if is_available:
                await cls._set_online(driver_id, ride_type, lat, lng, device_token)
            else:
                await cls._set_offline(driver_id, ride_type)
        except Exception as e:
            LOG.error(
                f"update_driver_status failed | driver={driver_id} "
                f"is_available={is_available} | error={e}",
                exc_info=True
            )
            raise  # Let the service layer handle the HTTP response

    @classmethod
    async def _set_online(
        cls,
        driver_id: int,
        ride_type: str,
        lat: float,
        lng: float,
        device_token: str,
    ):
        meta_key = cls._meta_key(driver_id)
        alive_key = cls._alive_key(driver_id)
        geo_key = cls._geo_key(ride_type)

        async with redis_client.pipeline(transaction=False) as pipe:
            # 1. Add to geo index
            pipe.geoadd(geo_key, (lng, lat, str(driver_id)))

            # 2. Set meta fields — never overwrite a valid token with None/empty
            pipe.hset(meta_key, "ride_type", str(ride_type))
            if device_token:
                pipe.hset(meta_key, "device_token", str(device_token))
            pipe.hset(meta_key, "is_available", "1")

            # 3. Set TTL on meta so it auto-cleans if driver never logs out
            pipe.expire(meta_key, DRIVER_META_TTL)

            # 4. Alive key with TTL (heartbeat must renew this)
            pipe.setex(alive_key, DRIVER_ALIVE_TTL, "1")

            await pipe.execute()

        LOG.info(f"Driver {driver_id} online | ride_type={ride_type} | lat={lat} lng={lng}")

    @classmethod
    async def _set_offline(cls, driver_id: int, ride_type: str):
        meta_key = cls._meta_key(driver_id)
        alive_key = cls._alive_key(driver_id)
        geo_key = cls._geo_key(ride_type)

        async with redis_client.pipeline(transaction=False) as pipe:
            # 1. Remove from geo index (critical — else ghost drivers remain)
            pipe.zrem(geo_key, str(driver_id))

            # 2. Mark unavailable in meta
            pipe.hset(meta_key, "is_available", "0")

            # 3. Set short TTL on meta (cleanup after 5 min of being offline)
            pipe.expire(meta_key, 10)

            # 4. Delete alive key immediately
            pipe.delete(alive_key)

            await pipe.execute()

        LOG.info(f"Driver {driver_id} offline | ride_type={ride_type}")

    @classmethod
    async def update_driver_location(
        cls,
        driver_id: int,
        ride_type: str,
        lat: float,
        lng: float,
        device_token: str = None,
    ):
        """Refresh geo position + heartbeat without clearing a valid stored token."""
        await cls._set_online(driver_id, ride_type, lat, lng, device_token)
        await cls.refresh_heartbeat(driver_id)

    @classmethod
    async def refresh_heartbeat(cls, driver_id: int):
        """
        Driver app calls this every ~60s to stay alive.
        If this stops, driver:alive key expires and they become invisible
        to georadius searches automatically.
        """
        try:
            await redis_client.setex(
                cls._alive_key(driver_id), DRIVER_ALIVE_TTL, "1"
            )
            LOG.debug(f"Heartbeat refreshed for driver={driver_id}")
        except Exception as e:
            LOG.error(f"refresh_heartbeat failed | driver={driver_id} | error={e}")
            raise