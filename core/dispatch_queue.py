import json
import os
from typing import Any, Dict

from config.redis_config import redis_client

DISPATCH_QUEUE_KEY = os.getenv("DISPATCH_QUEUE_KEY", "dispatch:jobs")
DISPATCH_PROCESSING_QUEUE_KEY = os.getenv(
    "DISPATCH_PROCESSING_QUEUE_KEY", "dispatch:jobs:processing"
)
DISPATCH_ENQUEUED_TTL_SECONDS = int(
    os.getenv("DISPATCH_ENQUEUED_TTL_SECONDS", "600")
)


def _enqueued_dedup_key(ride_request_id: str) -> str:
    return f"ride:dispatch:enqueued:{ride_request_id}"


async def enqueue_dispatch_job(
    *,
    ride_request_id: str,
    ride_type: str,
    lat: float,
    lng: float,
    user_data: Dict[str, Any],
    user_id: int,
) -> bool:
    """
    Enqueue a dispatch job for a single ride.

    Returns:
        True if the job was enqueued (dedup key was newly set),
        False if it was already enqueued recently.
    """
    dedup_key = _enqueued_dedup_key(ride_request_id)
    was_set = await redis_client.set(
        dedup_key, "1", nx=True, ex=DISPATCH_ENQUEUED_TTL_SECONDS
    )
    if not was_set:
        return False

    job = {
        "ride_request_id": ride_request_id,
        "ride_type": ride_type,
        "lat": lat,
        "lng": lng,
        "user_data": user_data,
        "user_id": user_id,
    }

    await redis_client.lpush(DISPATCH_QUEUE_KEY, json.dumps(job))
    return True


async def dequeue_dispatch_job(timeout_seconds: int = 5) -> Dict[str, Any] | None:
    """
    Blocking dequeue from Redis list.
    Returns parsed job dict or None when timeout occurs.
    """
    # Atomically move job from "queue" -> "processing".
    # If worker crashes after dequeue, the job remains in processing list for requeue.
    job_str = await redis_client.brpoplpush(
        DISPATCH_QUEUE_KEY,
        DISPATCH_PROCESSING_QUEUE_KEY,
        timeout=timeout_seconds,
    )
    if not job_str:
        return None
    return json.loads(job_str)


async def requeue_processing_jobs() -> int:
    """
    Move jobs from processing list back into the main queue.
    Useful on worker startup after an unclean shutdown.
    """
    moved = 0
    while True:
        job_str = await redis_client.rpop(DISPATCH_PROCESSING_QUEUE_KEY)
        if not job_str:
            break
        await redis_client.lpush(DISPATCH_QUEUE_KEY, job_str)
        moved += 1
    return moved
