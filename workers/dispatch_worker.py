"""Dispatch worker: consumes Redis queue and runs DriverSearchService.start_wave."""

import asyncio
import logging
import os
from typing import Any, Dict, Set

from config import env_config  # noqa: F401 (loads .env)
from apps.v1.api.driver.services.driver_search_service import DriverSearchService
from core.dispatch_queue import dequeue_dispatch_job, requeue_processing_jobs

LOG = logging.getLogger(__name__)

DISPATCH_MAX_CONCURRENT = int(os.getenv("DISPATCH_MAX_CONCURRENT", "20"))
DISPATCH_LOOP_SLEEP_SECONDS = float(os.getenv("DISPATCH_LOOP_SLEEP_SECONDS", "0.2"))
DISPATCH_WORKER_ENABLED = os.getenv("DISPATCH_WORKER_ENABLED", "false").lower() == "true"


async def handle_job(job: Dict[str, Any], semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        await DriverSearchService.start_wave(
            ride_request_id=job["ride_request_id"],
            ride_type=job["ride_type"],
            lat=job["lat"],
            lng=job["lng"],
            user_data=job["user_data"],
            user_id=job["user_id"],
        )


async def run_dispatch_worker() -> None:
    """
    Long-running dispatch loop. Safe to run as asyncio.create_task()
  inside socket_server (or any async process with Redis access).
    """
    semaphore = asyncio.Semaphore(DISPATCH_MAX_CONCURRENT)
    tasks: Set[asyncio.Task] = set()

    try:
        moved = await requeue_processing_jobs()
        if moved:
            LOG.info("Requeued %s stale dispatch jobs from processing list", moved)
    except Exception:
        LOG.exception("Failed to requeue stale dispatch jobs")

    LOG.info(
        "Dispatch worker started | max_concurrent=%s queue_mode=redis_list",
        DISPATCH_MAX_CONCURRENT,
    )

    while True:
        job = await dequeue_dispatch_job(timeout_seconds=5)
        if not job:
            await asyncio.sleep(DISPATCH_LOOP_SLEEP_SECONDS)
            continue

        task = asyncio.create_task(handle_job(job, semaphore))
        tasks.add(task)

        done = {t for t in tasks if t.done()}
        tasks -= done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_dispatch_worker())
