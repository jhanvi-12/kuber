"""This module is used to work with redis and there functionality"""

import time

from core.utils import constant_variable

from config.redis_config import redis_client


class RedisRideRepo:
    """This class is used to represenst all ride methods to store data in redis."""

    @classmethod
    def init_search_state(cls, ride_id, pickup_lat, pickup_lng):
        """Initiate the driver search."""
        key = f"ride:search:{ride_id}"

        redis_client.hmset(
            key,
            mapping={
                "status": "SEARCHING",
                "wave": 1,
                "pickup_lat": pickup_lat,
                "pickup_lng": pickup_lng,
                "created_at": int(time.time())
            }
        )

        redis_client.expire(key, 300)  # 5 min safety TTL

    @classmethod
    def acquire_lock(cls, ride_id, ttl=30):
        """
        Prevents multiple drivers from accepting same ride
        """
        lock_key = f"ride:lock:{ride_id}"
        return redis_client.set(lock_key, "1", nx=True, ex=ttl)

    @classmethod
    def release_lock(cls, ride_id):
        """Prevents release lock.

        Args:
            ride_id (int): Ride id.
        """
        redis_client.delete(f"ride:lock:{ride_id}")

    @classmethod
    def update_status(cls, ride_id, status):
        """Updating the ride status to make to customer is aware."""
        redis_client.hset(
            f"ride:search:{ride_id}",
            "status",
            status
        )

    @classmethod
    def get_status(cls, ride_id):
        """Fetching the status of the ride."""
        return redis_client.hget(
            f"ride:search:{ride_id}",
            "status"
        )

    @classmethod
    def get_wave(cls, ride_id):
        """This method is used to fetch the waves"""
        return int(redis_client.hget(
            f"ride:search:{ride_id}", "wave"
        ) or 1)

    @classmethod
    def increment_wave(cls, ride_id):
        """This method is used to increment wave count."""
        redis_client.hincrby(
            f"ride:search:{ride_id}",
            "wave",
            1
        )

    @classmethod
    def add_candidates(cls, ride_id, drivers):
        """This method is used to add drivers with that matching ride_type."""
        key = f"ride:candidates:{ride_id}"
        redis_client.sadd(key, *drivers)
        redis_client.expire(key, 300)

    @classmethod
    def has_driver_been_notified(cls, ride_id, driver_id):
        """This method is keep track that drivers recevied the notification."""
        return redis_client.sismember(
            f"ride:candidates:{ride_id}",
            driver_id
        )

    # -------------------------------
    # Accept Ride (ATOMIC)
    # -------------------------------
    @classmethod
    def mark_accepted(cls, ride_id, driver_id):
        """
        Returns False if ride already accepted
        """
        if not cls.acquire_lock(ride_id):
            return False

        redis_client.hset(
            f"ride:search:{ride_id}",
            mapping={
                "status": "ACCEPTED",
                "driver_id": driver_id,
                "accepted_at": int(time.time())
            }
        )
        return True


class RedisDriverRepo:
    """This class is used to store the drivers related details"""

    @staticmethod
    def _geo_key(ride_type: str):
        return f"drivers:geo:{ride_type}"

    @classmethod
    def set_available(
        cls,
        driver_id: int,
        lat: float,
        lon: float,
        ride_type: str,
        device_token: str
    ):
        """This method is storing the geo location and ride_type, along with device_token."""
        # 1️⃣ Store geo location
        redis_client.geoadd(cls._geo_key(ride_type),(lon, lat, str(driver_id)))

        # 2️⃣ Store metadata
        redis_client.hmset(
            f"driver:meta:{driver_id}",
            mapping={
                "ride_type": ride_type,
                "device_token": device_token,
                "is_available": constant_variable.STATUS_ONE
            }
        )

        # ✅ Heartbeat
        redis_client.setex(
            f"driver:alive:{driver_id}",
            300,
            1
        )

    @classmethod
    def set_unavailable(cls, driver_id: int, ride_type: str):
        """This method is used to remove that unavailable drivers from redis"""
        # Remove from geo search
        redis_client.zrem(
            cls._geo_key(ride_type),
            str(driver_id)
        )

        # Update metadata
        redis_client.hset(
            f"driver:meta:{driver_id}",
            "is_available",
            constant_variable.STATUS_ZERO
        )
