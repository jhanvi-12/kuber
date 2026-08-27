"""This module is responsible for the socket server implementation."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import parse_qs

import socketio
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession

from config import env_config
from config.db_session import session_factory
from config.redis_config import (
    REDIS_BROKER_URL,
    SOCKET_CHANNEL,
    redis_client,
    redis_pubsub_client,
)
from apps.v1.api.auth.models.attribute import UserTypeEnum
from core.utils.helper import send_request
from core.utils.message_variable import *
from core.utils.session_auth import validate_token_session
from core.utils.token_authentication import JWTOAuth2
from core.redis_repo import RedisDriverRepo
from workers.dispatch_worker import DISPATCH_WORKER_ENABLED, run_dispatch_worker

LOG = logging.getLogger(__name__)
REDIS_LISTENER_MAX_FAILURES = 8
REDIS_LISTENER_MAX_BACKOFF_SECONDS = 15

backend_url = env_config.BACKEND_URL

# Intialize the Socket.IO server
sio = socketio.AsyncServer(
    async_mode="aiohttp",
    cors_allowed_origins="*",
    client_manager=socketio.AsyncRedisManager(REDIS_BROKER_URL),
    ping_interval=25,
    ping_timeout=60,
    max_http_buffer_size=1_000_000,
)
# Create a web application
app = web.Application()

# Attach the Socket.IO server to the web application
sio.attach(app)

@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """This method is used to create the DB session for the socket events."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def _emit_socket_payload(raw_data):
    """Parse a Redis pub/sub payload and emit it to the Socket.IO room."""
    try:
        payload = json.loads(raw_data)
        event = payload.get("event")
        data = payload.get("data")
        room = payload.get("room")

        if not event or data is None:
            LOG.warning("Invalid socket payload: %s", payload)
            return

        if not room:
            LOG.warning("Skipped '%s': no room in payload", event)
            return

        await sio.emit(event, data, room=room)
        LOG.info("Emitted '%s' to room '%s'", event, room)
    except json.JSONDecodeError:
        LOG.exception("Failed to parse Redis socket message")
    except Exception:
        LOG.exception("Error emitting Redis socket message")


async def _close_pubsub(pubsub):
    if pubsub is None:
        return
    try:
        await pubsub.unsubscribe(SOCKET_CHANNEL)
    except Exception:
        pass
    try:
        await pubsub.close()
    except Exception:
        pass


async def redis_event_listener():
    """
    Listen to Redis Pub/Sub and emit Socket.IO events.

    FastAPI publishes to SOCKET_CHANNEL; this process emits to connected clients.
    Reconnects on Redis drops so the listener does not stay dead until a manual restart.
    """
    backoff = 1
    failures = 0

    while True:
        pubsub = None
        try:
            pubsub = redis_pubsub_client.pubsub()
            await pubsub.subscribe(SOCKET_CHANNEL)
            LOG.info("Subscribed to Redis channel: %s", SOCKET_CHANNEL)
            failures = 0
            backoff = 1

            # timeout=None waits for the next Redis message and yields the
            # event loop. Do not use timeout=0/1 — that busy-polls and pegs CPU.
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=None,
                )
                if not msg or msg.get("type") != "message":
                    continue
                await _emit_socket_payload(msg.get("data"))

        except asyncio.CancelledError:
            LOG.info("Redis listener task cancelled")
            await _close_pubsub(pubsub)
            raise
        except Exception:
            failures += 1
            LOG.exception(
                "Redis listener error (%s/%s)", failures, REDIS_LISTENER_MAX_FAILURES
            )
            await _close_pubsub(pubsub)
            if failures >= REDIS_LISTENER_MAX_FAILURES:
                LOG.critical(
                    "Redis listener failed %s times; exiting so systemd can restart",
                    failures,
                )
                os._exit(1)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, REDIS_LISTENER_MAX_BACKOFF_SECONDS)

# Define event handlers
@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    print(f"Client connected: {sid}")
    query_string = environ.get("QUERY_STRING", "")
    params = parse_qs(query_string)
    token = params.get("token", [None])[0]

    if not token:
        print("Token missing. Disconnecting...")
        await sio.disconnect(sid)
        return

    try:
        user_data = JWTOAuth2().verify_access_token(token)
    except Exception:
        print("Invalid token. Disconnecting...")
        await sio.disconnect(sid)
        return

    if not await validate_token_session(user_data):
        await sio.emit(
            "auth_error",
            {"code": "SESSION_REVOKED", "message": "Session expired or invalid"},
            room=sid,
        )
        await sio.disconnect(sid)
        return

    user_id = user_data.get("user_id")
    user_type = user_data.get("user_type")

    await sio.save_session(sid, {
        "token": f"Bearer {token}",
        "user_id": user_id,
        "user_type": user_type,
    })
    print(f"Client connected | user_id={user_id} user_type={user_type}")

    if user_type == UserTypeEnum.CUSTOMER.value:
        await sio.enter_room(sid, f"user:{user_id}")
        print(f"{sid} auto-joined user:{user_id}")

    if user_type == UserTypeEnum.DRIVER.value:
        await sio.enter_room(sid, f"driver:{user_id}")
        print(f"{sid} auto-joined driver:{user_id}")

    await sio.emit(
        "response",
        {
            "message": "Welcome to the Socket.IO server!",
            "user_id": user_id,
            "user_type": user_type,
        },
        room=sid,
    )


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    print(f"Client disconnected: {sid}")

async def get_authenticated_user(sid):
    """
    Generic helper to get user/driver from socket session using JWT token.

    Returns payload dict if valid, None otherwise.
    Emits proper auth_error events if token missing/invalid.
    """
    session = await sio.get_session(sid)
    token = session.get("token")

    if not token:
        await sio.emit(
            "auth_error",
            {"code": "TOKEN_MISSING", "message": "Authentication required"},
            room=sid
            )
        return False 

    try:
        data = JWTOAuth2().verify_access_token(token.split(" ")[1])
        if not await validate_token_session(data):
            await sio.emit(
                "auth_error",
                {"code": "SESSION_REVOKED", "message": "Session expired or invalid"},
                room=sid,
            )
            await sio.disconnect(sid)
            return False
        return data
    except Exception:
        await sio.emit(
            "auth_error",
            {"code": "TOKEN_INVALID", "message": "Session expired or Invalid!"},
            room=sid
        )
        return False

@sio.on("driver_location_update")
async def driver_location_update(sid, data):
    """
    Driver sends live location updates every 3 to 5 seconds
    """
    try:
        driver_data = await get_authenticated_user(sid)
        if not driver_data:
            return
        driver_id = driver_data["user_id"]

        if isinstance(data, (str, bytes, bytearray)):
            data = json.loads(data)
        elif not isinstance(data, dict):
            return

        lat = data.get("lat")
        lng = data.get("lng")
        ride_type = data.get("ride_type")
        device_token = data.get("device_token")

        if lat is None or lng is None or not ride_type:
            return

        lat = float(lat)
        lng = float(lng)

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return

        await RedisDriverRepo.update_driver_location(
            driver_id, ride_type, lat, lng, device_token,
        )

        tracking = await RedisDriverRepo.get_driver_tracking(driver_id)
        user_id = tracking.get("user_id")
        if user_id:
            await sio.emit(
                "driver_location",
                {
                    "driver_id": driver_id,
                    "lat": lat,
                    "lng": lng,
                },
                room=f"user:{int(user_id)}",
            )
            print(
                f"driver_location_update Successfully emitted 'driver_location' "
                f"driver_id={driver_id}  lat={lat}  lng={lng}"
            )

    except Exception as e:
        print("driver_location_update error: %s", str(e))

@sio.on("join_room")
async def join_room(sid, data):
    """
    Customer joins ride:{ride_request_id} after booking.
    FE must emit: join_room { "ride_request_id": "<uuid>" }
    """
    user_data = await get_authenticated_user(sid)
    if not user_data:
        return

    if isinstance(data, str):
        data = json.loads(data)

    ride_request_id = data.get("ride_request_id") or data.get("ride_id")
    if not ride_request_id:
        await sio.emit(
            "error",
            {"message": "ride_request_id is required"},
            room=sid,
        )
        return

    redis_key = f"ride:search:{ride_request_id}"
    ride_req = await redis_client.hgetall(redis_key)
    if not ride_req:
        await sio.emit(
            "error",
            {"message": "Ride not found or expired"},
            room=sid,
        )
        return

    if str(ride_req.get("user_id")) != str(user_data["user_id"]):
        await sio.emit(
            "error",
            {"message": "Not authorized for this ride"},
            room=sid,
        )
        return

    room_name = f"ride:{ride_request_id}"
    await sio.enter_room(sid, room_name)
    print(f"{sid} joined {room_name}")
    await sio.emit(
        "room_joined",
        {"room": room_name, "ride_request_id": ride_request_id},
        room=sid,
    )

async def start_background_tasks(app):
    """Function to start the background tasks."""
    app["redis_task"] = asyncio.create_task(redis_event_listener())

    # Run dispatch worker in-process (no extra systemd service needed).
    # Enable only on the socket service unit via DISPATCH_WORKER_ENABLED=true.
    if DISPATCH_WORKER_ENABLED:
        app["dispatch_worker_task"] = asyncio.create_task(run_dispatch_worker())
        print("Dispatch worker started inside socket_server process")
    else:
        app["dispatch_worker_task"] = None
        print("Dispatch worker disabled (set DISPATCH_WORKER_ENABLED=true to enable)")

async def cleanup_background_tasks(app):
    """Function to clean the background tasks."""
    app["redis_task"].cancel()
    dispatch_task = app.get("dispatch_worker_task")
    if dispatch_task:
        dispatch_task.cancel()

app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

# Run the socket server
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("Socket.IO server is running")
    web.run_app(
        app, host=env_config.SOCKET_SERVER_HOST, port=int(env_config.SOCKET_SERVER_PORT)
    )
