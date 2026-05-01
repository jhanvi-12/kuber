"""This module is used to work with redis and there functionality"""

import time

from apps.v1.api.ride.models.attribute import RideStatusEnum
from config.redis_config import redis_client
from core.utils import constant_variable


class RedisRideRepo:
    """This class is used to represenst all ride methods to store data in redis."""

    @classmethod
    async def init_search_state(cls, ride_request_id: str, user_id: int, payload: dict):
        """Initiate the driver search."""
        key = f"ride:search:{ride_request_id}"

        data = {
            "status": "Searching",
            "user_id": user_id,
            "pickup_latitude": payload["pickup_latitude"],
            "pickup_longitude": payload["pickup_longitude"],
            "pickup_address": payload["pickup_address"],
            "destination_latitude": payload["destination_latitude"],
            "destination_longitude": payload["destination_longitude"],
            "destination_address": payload["destination_address"],
            "ride_type": payload["ride_type"],
            "ride_fare": payload["ride_fare"],
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
        Atomically marks driver as notified.
        Returns True only if driver was NOT notified before.
        """
        return await redis_client.sadd(
            f"ride:candidates:{ride_id}",
            driver_id
        )

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

    @classmethod
    async def set_available(
        cls,
        driver_id: int,
        lat: float,
        lon: float,
        ride_type: str,
        device_token: str
    ):
        """This method is storing the geo location and ride_type, along with device_token."""
        # Store geo location
        await redis_client.geoadd(cls._geo_key(ride_type),(lon, lat, str(driver_id)))

        # Store metadata
        await redis_client.hmset(
            f"driver:meta:{driver_id}",
            mapping={
                "ride_type": ride_type,
                "device_token": device_token,
                "is_available": constant_variable.STATUS_ONE
            }
        )

        # Heartbeat
        await redis_client.setex(
            f"driver:alive:{driver_id}",
            1000,
            1
        )

    @classmethod
    async def set_unavailable(cls, driver_id: int, ride_type: str):
        """This method is used to remove that unavailable drivers from redis"""
        # Remove from geo search
        await redis_client.zrem(
            cls._geo_key(ride_type),
            str(driver_id)
        )

        # Update metadata
        await redis_client.hset(
            f"driver:meta:{driver_id}",
            "is_available",
            constant_variable.STATUS_ZERO
        )
