"""This module is used for the redis configuration with host and port details."""
import os

import redis

from core.utils import constant_variable

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_BROKER_URL = os.environ.get("REDIS_BROKER_URL")



redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=constant_variable.STATUS_TRUE,
)
