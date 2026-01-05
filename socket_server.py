"""This module is responsible for the socket server implementation."""

import json
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

import socketio
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession
from core.utils import constant_variable
from apps.v1.api.ride.services.get_ride_details_service import RideDetailService
from apps.v1.api.ride.services.accept_ride_service import RideAcceptService
from config import env_config
from core.redis_repo import RedisDriverRepo, RedisRideRepo
from core.utils.helper import send_request
from core.utils.message_variable import *
from core.utils.token_authentication import JWTOAuth2
from typing import AsyncGenerator
from config.db_session import session_factory

backend_url = env_config.BACKEND_URL

# Intialize the Socket.IO server
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")

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

    # Save token in the socket session
    await sio.save_session(sid, {"token": f"Bearer {token}"})
    print(f"Client connected with token: {token}")

    await sio.emit(
        "response", {"message": "Welcome to the Socket.IO server!"}, room=sid
    )


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    print(f"Client disconnected: {sid}")

async def get_authenticated_user(sid, required=True):
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
    Driver sends live location updates every 3–5 seconds
    """
    try:
        # 1️⃣ Get authenticated driver_id from socket session
        driver_data = await get_authenticated_user(sid)
        if not driver_data:
            return
        driver_id = driver_data["user_id"]

        # 2️⃣ Extract & validate payload
        data = json.loads(data)
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

        # 3️⃣ Update GEO location (RAW COMMAND – SAFE)
        RedisDriverRepo.set_available(
            driver_id,
            lat,
            lng, ride_type, device_token
        )

        await sio.emit(
            "driver_location",
            {
                "driver_id": driver_id,
                "lat": lat,
                "lng": lng
            }
        )

    except Exception as e:
        # Log only — never crash socket server
        print("driver_location_update error:", str(e))

@sio.on("get_ride_details")
async def get_ride_details(sid, data):
    """This event is used to get the ride details for the driver."""
    ride_data = await get_authenticated_user(sid)
    if not ride_data:
        return

    data = json.loads(data)
    ride_id = data["ride_id"]
    driver_id = ride_data["user_id"]
    
    # Calling the BE service to fetch the ride details.
    async with get_async_session() as db:
        ride_payload = await RideDetailService().get_ride_details(db, ride_id, driver_id)
        if ride_payload.status_code != constant_variable.STATUS_CODE_200:
            await sio.emit("ride_error",
                               json.loads(ride_payload.body)
                           )
        else:
            await sio.emit(
                "ride_details", 
                json.loads(ride_payload.body)["data"],
                sid)

@sio.on("accept_ride")
async def accept_ride(sid, data):
    """This event is used to accept the ride driver."""
    ride_data = await get_authenticated_user(sid)
    if not ride_data:
        return

    data = json.loads(data)
    ride_id = data["ride_id"]
    driver_id = ride_data["user_id"]
    print("DAta", driver_id, ride_id)
    # STEP 1: Redis lock FIRST
    if not RedisRideRepo.acquire_lock(ride_id, driver_id):
        await sio.emit(
            "ride_already_taken",
            {"message": ErrorMessage.rideAlreadyAccepted},
            room=sid
        )
        return
    # Calling the BE service to fetch the ride details.
    async with get_async_session() as db:
        ride_payload = await RideAcceptService().ride_accepted_service(db, ride_id, driver_id)
        if ride_payload.status_code != constant_variable.STATUS_CODE_200:
            await sio.emit("ride_error",
                               json.loads(ride_payload.body)
                           )
        else:
            await sio.emit(
                "ride_accepted",
                {
                    "status": InfoMessage.reqAccepted,
                    "message": InfoMessage.driverHeading,
                    "data": json.loads(ride_payload.body)["data"],
                },
                sid)

@sio.on("reached_location")
async def reached_location(sid, data):
    ride_data = await get_authenticated_user(sid)
    if not ride_data:
        return

    data = json.loads(data)
    ride_id = data["ride_id"]
    driver_id = ride_data["user_id"]

    # Guard 1: ride must exist in Redis
    # status = RedisRideRepo.get_status(ride_id)
    # if status != "ACCEPTED":
    #     await sio.emit(
    #         "invalid_ride_state",
    #         {"message": "Ride not in accepted state"},
    #         room=sid,
    #         namespace="/driver"
    #     )
    #     return

    # Guard 2: same driver only
    assigned_driver = RedisRideRepo.get_assigned_driver(ride_id)
    if assigned_driver != driver_id:
        await sio.emit(
            "unauthorized_action",
            {},
            sid
        )
        return

    # ✅ Update Redis
    RedisRideRepo.update_status(ride_id, "DRIVER_ARRIVED")

    # ✅ Update DB (persistent)
    async with get_async_session() as db:
        res = await RideAcceptService().driver_reached_service(
            db, ride_id, driver_id
        )
        if res.status_code != constant_variable.STATUS_CODE_200:
            await sio.emit("ride_error",
                            json.loads(res.body)
                           )
        else:
            # 📣 Notify customer
            await sio.emit(
                "driver_reached",
                {
                    "ride_id": ride_id,
                    "status": InfoMessage.arrivedNow,
                    "message": "Driver has arrived at your location"
                },
                sid
            )

@sio.on("join_ride", namespace="/")
async def join_ride(sid, data):
    data = json.loads(data)
    ride_id = data["ride_id"]

    await sio.enter_room(
        sid,
        f"ride:{ride_id}",
        namespace="/"
    )

    # ✅ confirmation event (VERY IMPORTANT)
    await sio.emit(
        "join_ride_success",
        {
            "ride_id": ride_id,
            "room": f"ride:{ride_id}"
        },
        to=sid
    )


# 1st event
@sio.event
async def track_driver(sid, data):
    """Handle driver tracking with live location."""
    print(f"Received track_driver: {data}")
    try:
        session = await sio.get_session(sid)
        token = session.get("token")
        # Call backend API to get driver location
        response = send_request(
            "POST",
            f"{backend_url}user/ride/track_driver",
            {"authorization": token},
            json_header=True,
            data=data,
        )

        try:
            data = response.json()
        except Exception:
            data = {"message": "Invalid JSON from backend"}

        print(f"Driver location response: {data}")
        if response.status_code != 200:
            await sio.emit("error", {"data": data}, room=sid)
        else:
            await sio.emit("driver_location", {"data": data}, room=sid)

    except Exception as e:
        print(f"Error: {e}")
        await sio.emit("error", {"message": ErrorMessage.generalTryAgain}, room=sid)


# 2nd event
@sio.event
async def ride_event(sid, data):
    """Handle ride acceptance."""
    print(f"ride_event received with data {data}")
    try:
        session = await sio.get_session(sid)
        token = session.get("token")
        # Here you can process the ride acceptance logic and calling the backend API
        response = send_request(
            "POST",
            f"{backend_url}user/ride",
            {"authorization": token},
            json_header=True,
            data=data,
        )
        if response.status_code != 200:
            print(f"Failed to accept ride: {response}")
            await sio.emit("error", {"message": ErrorMessage.failedtoAccept}, room=sid)

        print(f"Ride Started by driver: %s {response.json()}")

        data = response.json()
        await sio.emit(
            "ride_started",
            {"data": data},
            room=sid,
        )
    except Exception as e:
        print(f"Error processing ride started: {e}")
        await sio.emit("error", {"message": ErrorMessage.generalTryAgain}, room=sid)


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
        # Emit event to user that driver arrived
        await sio.emit(
            "ride_cancelled",
            {"data": data},
        )

    except Exception as e:
        print(f"Error: {e}")
        await sio.emit("error", {"message": ErrorMessage.generalTryAgain}, room=sid)


# Run the socket server
if __name__ == "__main__":
    print("Socket.IO server is running")
    web.run_app(
        app, host=env_config.SOCKET_SERVER_HOST, port=int(env_config.SOCKET_SERVER_PORT)
    )
