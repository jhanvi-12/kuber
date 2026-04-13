"""This module is responsible to contain ride API's endpoint"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.pagination_service import oauth2
from apps.v1.api.ride import schema
from apps.v1.api.ride.services.accept_ride_service import RideAcceptService
from apps.v1.api.ride.services.book_ride_service import BookRideService
from apps.v1.api.ride.services.ride_otp_verify_service import RideOTPService
from apps.v1.api.ride.services.cancel_ride_service import UserRideCancelService
from apps.v1.api.ride.services.get_ride_details_service import RideDetailService
from config import db_config
from core.utils.token_authentication import JWTOAuth2

getdb = db_config.get_db

riderouter = APIRouter()


@riderouter.post("/book_ride")
async def book_ride_api(
    body: schema.BookRideSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
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
    response = await BookRideService().create_book_ride_service(db, body, current_user)
    return response

@riderouter.post("/ride/cancel_before_booking")
async def before_cancel_ride_api(
    ride_request_id: str,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
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
    response = await UserRideCancelService().before_book_ride_cancel_service(
        db, ride_request_id, current_user
    )
    return response


@riderouter.post("/ride_accept")
async def accept_ride_api(
    ride_request_id: str,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """Accept Ride API

    Args:
        ride_request_id (str): Ride ID
        db (AsyncSession, optional): DB session. Defaults to Depends(getdb).
        authorize (HTTPAuthorizationCredentials, optional): JWT token to authorize.

    Returns:
        dict: A response indicating the success or failure of the ride cancellation.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideAcceptService().ride_accepted_service(
        db, ride_request_id, current_user
    )
    return response


@riderouter.post("/ride/update_status")
async def update_ride_status_api(
    body: schema.RideStatusSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Endpoint when the driver's reached to the location.

    Args:
        body (dict): The request body containing ride and driver IDs.
      db (AsyncSession): The database session.
    Returns:
       dict: A response containing the driver's ride reached status.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideDetailService().update_ride_status_service(
        db, current_user, body.dict()
    )
    return response

@riderouter.get("/my_rides")
async def my_rides_api(
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to fetch the ride details of customer.
    Args:
         db (AsyncSession): The database session.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideDetailService().fetch_user_rides_service(
        db, current_user
    )
    return response

@riderouter.post("/ride/cancel_after_booking")
async def cancel_ride_api(
    body: schema.RideCancleSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
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
        db, body.dict(), current_user
    )
    return response

@riderouter.post("/ride/otp_verify")
async def ride_otp_verify_api(
    body: schema.RideOTPShema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Endpoint to verify the a ride otp.

    Args:
        otp (int): OTP to verify.
        db (AsyncSession): The database session.

    Returns:
        dict: A response indicating the success or failure of the ride cancellation.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideOTPService().ride_otp_verification_service(
        db, body, current_user
    )
    return response
