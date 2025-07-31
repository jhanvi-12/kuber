"""This module is responsible to contain ride API's endpoint"""

from fastapi import APIRouter, Depends, Body
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.pagination_service import oauth2
from apps.v1.api.ride import schema
from apps.v1.api.ride.services.accept_ride_service import RideAcceptService
from apps.v1.api.ride.services.book_ride_service import BookRideService
from apps.v1.api.ride.services.cancel_ride_service import UserRideCancelService
from apps.v1.api.ride.services.track_driver_service import TrackRideService
from config import db_config
from core.utils.token_authentication import JWTOAuth2

getdb = db_config.get_db

riderouter = APIRouter()


@riderouter.post("/book_ride")
async def book_ride_api(
    body: schema.BookRideSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to book a ride.

    Args:
        request (Request): The FastAPI request object.
        db (AsyncSession): The database session.

    Returns:
        dict: A response indicating the success or failure of the ride booking.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await BookRideService().create_book_ride_service(
        db, body, current_user
    )
    return response

@riderouter.post("/ride")
async def start_ride_api(
    body: dict,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to accept a ride.

    Args:
        ride_id (int): The ID of the ride to accept.
        db (AsyncSession): The database session.

    Returns:
        dict: A response indicating the success or failure of the ride acceptance.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideAcceptService().user_start_ride_service(current_user, db, body)
    return response

@riderouter.post("/ride/track_driver")
async def track_driver_api(
    body: dict,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to track the driver's live location.

    Args:
        body (dict): The request body containing ride and driver IDs.
        db (AsyncSession): The database session.

    Returns:
        dict: A response containing the driver's current location.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await TrackRideService().user_track_driver_service(current_user, db, body)
    return response

@riderouter.post("/ride/update_status")
async def driver_reached_api(
    body: dict,
    db: AsyncSession = Depends(getdb)
):
    """
    Endpoint to update the ride status when the driver reaches the pickup location.

    Args:
        body (DriverReachedSchema): The request body containing ride details.
        db (AsyncSession): The database session.

    Returns:
        dict: A response indicating the success or failure of the status update.
    """
    response = await RideAcceptService().driver_reached_service(
        db, body
    )
    return response

@riderouter.post("/ride/cancel")
async def cancel_ride_api(
    body: dict = Body(...),
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to cancel a ride.

    Args:
        ride_id (int): The ID of the ride to cancel.
        db (AsyncSession): The database session.

    Returns:
        dict: A response indicating the success or failure of the ride cancellation.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await UserRideCancelService().user_ride_cancel_service(
        db, body, current_user
    )
    return response
