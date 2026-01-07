"""This module is used to work with redis and there functionality"""

import time

from core.utils import constant_variable

from config.redis_config import redis_client


class RedisRideRepo:
    """This class is used to represenst all ride methods to store data in redis."""

    @classmethod
    def init_search_state(cls, ride_request_id: str, user_id: int, payload: dict):
        """Initiate the driver search."""
        key = f"ride:search:{ride_request_id}"

        data = {
            "status": "SEARCHING",
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

        pipe = redis_client.pipeline()

        # Store ride request
        pipe.hmset(key, mapping=data)

        # Safety TTL (auto cleanup)
        pipe.expire(key, 600)  # 10 minutes

        # Cleanup related keys (if any)
        pipe.delete(f"ride:lock:{ride_request_id}")
        pipe.delete(f"ride:candidates:{ride_request_id}")

        pipe.execute()

    @classmethod
    def acquire_lock(cls, ride_request_id, driver_id):
        """
        Prevents multiple drivers from accepting same ride
        """
        lock_key = f"ride:lock:{ride_request_id}"
        is_locked = redis_client.setnx(lock_key, driver_id)
        if not is_locked:
            return False

        redis_client.expire(lock_key, 600)
        return True

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
    def add_candidates(cls, ride_request_id: str, driver_ids: list):
        """This method is used to add drivers with that matching ride_type."""
        key = f"ride:candidates:{ride_request_id}"

        if not driver_ids:
            return

        pipe = redis_client.pipeline()
        pipe.sadd(key, *driver_ids)

        # Keep same TTL as ride request (safety)
        pipe.expire(key, 600)  # 10 minutes

        pipe.execute()

    @classmethod
    def has_driver_been_notified(cls, ride_request_id: str, driver_id):
        """This method is keep track that drivers recevied the notification."""
        return redis_client.sismember(
            f"ride:candidates:{ride_request_id}",
            driver_id
        )

    @classmethod
    def get_assigned_driver(cls, ride_request_id: str):
        """
        Returns the driver_id who has locked/accepted the ride.
        Returns None if no driver is assigned.
        """
        key = f"ride:lock:{ride_request_id}"

        driver_id = redis_client.get(key)
        if not driver_id:
            return None

        # Redis returns bytes → convert to int
        return int(driver_id)

    # -------------------------------
    # Accept Ride (ATOMIC)
    # -------------------------------
    @classmethod
    def mark_accepted(cls, ride_request_id: str, driver_id: int):
        """
        Returns False if ride already accepted
        """
        if not cls.acquire_lock(ride_request_id, driver_id):
            return False

        redis_client.hmset(
            f"ride:search:{ride_request_id}",
            mapping={
                "status": "ACCEPTED",
                "driver_id": driver_id,
                "accepted_at": int(time.time())
            }
        )
        return True

    @classmethod
    def mark_rejected(cls, ride_request_id, driver_id):
        """This method is used when ride is rejected by driver"""
        redis_client.sadd(f"ride:rejected:{ride_request_id}", driver_id)
        redis_client.expire(f"ride:rejected:{ride_request_id}", 300)

    @classmethod
    def get_db_ride_id(cls, ride_request_id: str) -> int | None:
        key = f"ride:search:{ride_request_id}"
        ride_id = redis_client.hget(key, "ride_id")
        return int(ride_id) if ride_id else None


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
            1000,
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
