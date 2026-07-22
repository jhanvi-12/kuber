"""This module is responsible for the socket server implementation."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import parse_qs

import socketio
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession

from config import env_config
from config.db_session import session_factory
from config.redis_config import REDIS_BROKER_URL, SOCKET_CHANNEL, redis_client
from apps.v1.api.auth.models.attribute import UserTypeEnum
from core.utils.helper import send_request
from core.utils.message_variable import *
from core.utils.token_authentication import JWTOAuth2
from core.redis_repo import RedisDriverRepo
from workers.dispatch_worker import DISPATCH_WORKER_ENABLED, run_dispatch_worker

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

async def redis_event_listener():
    """
    Listen to Redis Pub/Sub and emit Socket.IO events.
    This bridges your FastAPI services to Socket.IO clients.
    """
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(SOCKET_CHANNEL)
        print(f"Subscribed to Redis channel: {SOCKET_CHANNEL}")

        async for msg in pubsub.listen():
            if msg["type"] == "subscribe":
                print(f"Successfully subscribed to {msg['channel']}")
                continue

            if msg["type"] != "message":
                continue

            try:
                # Parse the message payload
                payload = json.loads(msg["data"])
                event = payload.get("event")
                data = payload.get("data")
                room = payload.get("room")

                if not event or data is None:
                    print(f" Invalid payload: {payload}")
                    continue

                # Emit to Socket.IO clients
                if room:
                    await sio.emit(event, data, room=room)
                    print(f"Emitted '{event}' to room '{room}'")
                else:
                    print(f"Skipped '{event}': no room in payload (avoid global broadcast)")

            except json.JSONDecodeError as e:
                print(f"Failed to parse message: {e}")
            except Exception as e:
                print(f" Error handling message: {e}")

    except asyncio.CancelledError:
        print("Redis listener task cancelled")
    except Exception as e:
        print(f" Redis listener error: {e}")
    finally:
        await pubsub.unsubscribe(SOCKET_CHANNEL)
        await pubsub.close()
        print("Redis listener stopped")

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
        # Get authenticated driver_id from socket session
        driver_data = await get_authenticated_user(sid)
        if not driver_data:
            return
        driver_id = driver_data["user_id"]

        # Extract & validate payload
        # Socket.IO may deliver data as a dict (already parsed) or as a JSON string
        if isinstance(data, (str, bytes, bytearray)):
            data = json.loads(data)
        elif not isinstance(data, dict):
            return  # unexpected payload type, silently ignore

        lat = data.get("lat")
        lng = data.get("lng")
        ride_type = data.get("ride_type")
        device_token = data.get("device_token")

        if lat is None or lng is None or not ride_type:
            return  # silently ignore bad packets

        lat = float(lat)
        lng = float(lng)

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return

        # Update GEO location and keep heartbeat alive
        await RedisDriverRepo.update_driver_location(
            driver_id,
            ride_type,
            lat,
            lng,
            device_token,
        )

        await sio.emit(
            "driver_location",
            {
                "driver_id": driver_id,
                "lat": lat,
                "lng": lng
            }
        )
        print(
            f"driver_location_update Successfully emitted 'driver_location' driver_id={driver_id}  lat={lat}  lng={lng}"
        )
    except Exception as e:
        # Log only never crash socket server
        print("driver_location_update error:", str(e))

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

# 3rd event
@sio.event
async def cancel_ride(sid, data):
    """Handle driver or user cancel event."""
    print(f"Cancelled Ride event called: {data}")
    try:
        # Call backend API to update DB
        session = await sio.get_session(sid)
        token = session.get("token")

        response = send_request(
            "POST",
            f"{backend_url}user/ride/cancel",
            {"Authorization": token},
            data=data,
        )

        if response.status_code != 200:
            error_message = response.json().get(
                "detail", "Failed to cancel ride status"
            )
            await sio.emit("error", {"message": error_message}, room=sid)

        data = response.json()
        session = await sio.get_session(sid)
        user_id = session.get("user_id")
        target_room = f"user:{user_id}" if user_id else sid
        await sio.emit(
            "ride_cancelled",
            {"data": data},
            room=target_room,
        )

    except Exception as e:
        print(f"Error: {e}")
        await sio.emit("error", {"message": ErrorMessage.generalTryAgain}, room=sid)


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
    print("Socket.IO server is running")
    web.run_app(
        app, host=env_config.SOCKET_SERVER_HOST, port=int(env_config.SOCKET_SERVER_PORT)
    )
