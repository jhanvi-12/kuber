"""This module is used for the redis configuration with host and port details."""
import os

import redis.asyncio as redis

from core.utils import constant_variable

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_BROKER_URL = os.environ.get("REDIS_BROKER_URL")
SOCKET_CHANNEL = os.environ.get("SOCKET_CHANNEL", "socket:events")

_REDIS_KWARGS = {
    "host": REDIS_HOST,
    "port": REDIS_PORT,
    "decode_responses": constant_variable.STATUS_TRUE,
    "socket_keepalive": constant_variable.STATUS_TRUE,
    "health_check_interval": 30,
    "socket_connect_timeout": 10,
    "retry_on_timeout": constant_variable.STATUS_TRUE,
}

# Shared client for GET/SET/geo/publish from API and socket handlers.
redis_client = redis.Redis(**_REDIS_KWARGS)

# Dedicated client for socket pub/sub so a dropped subscriber cannot
# poison the shared command connection.
redis_pubsub_client = redis.Redis(**_REDIS_KWARGS)
