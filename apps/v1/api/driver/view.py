"""This module is responsible to contain driver API's endpoint"""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from apps.v1.api.ride.services.get_ride_details_service import RideDetailService
from apps.v1.api.auth.models import attribute
from apps.v1.api.driver import schema
from apps.v1.api.driver.services.create_driver_vehicle_service import \
    DriverService
from apps.v1.api.driver.services.driver_plan_service import DriverPlanService
from apps.v1.api.driver.services.get_driver_veh_service import GetDriverService
from apps.v1.api.driver.services.update_driver_status_service import \
    UpdateDriverStatusService
from apps.v1.api.pagination_service import oauth2
from apps.v1.api.ride.schema import LocationSchema
from config import db_config
from core.utils.token_authentication import JWTOAuth2
from apps.v1.api.auth.services.user_profile_service import UserProfileService

driverrouter = APIRouter()
getdb = db_config.get_db

@driverrouter.post("/vehicle/complete-profile")
async def driver_vehicle_complete_profile(
    request: Request,
    body: schema.DriverVehicleCombinedSchema = Depends(
        schema.DriverVehicleCombinedSchema.as_form
    ),

    # -------- Images --------
    rc_image: UploadFile = File(...),
    license_front_image: UploadFile = File(...),
    license_back_image: UploadFile = File(...),
    vehicle_image: UploadFile = File(...),
    vehicle_insurance_image: UploadFile = File(...),

    # -------- Common deps --------
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Combined API to:
    - Save vehicle details
    - Upload license & vehicle documents
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)

    response = await DriverService().create_driver_vehicle_and_docs_service(
        request=request,
        db=db,
        body=body,
        files={
            "license_front_image": license_front_image,
            "license_back_image": license_back_image,
            "rc_image": rc_image,
            "vehicle_image": vehicle_image,
            "vehicle_insurance_image": vehicle_insurance_image,
        },
        current_user=current_user,
    )
    return response

@driverrouter.put("/vehicle/update-profile")
async def driver_vehicle_update_profile(
    request: Request,
    body: schema.DriverVehicleCombinedSchema = Depends(
        schema.DriverVehicleCombinedSchema.as_form
    ),

    # -------- Images (Optional for update) --------
    rc_image: UploadFile = File(None),
    license_front_image: UploadFile = File(None),
    license_back_image: UploadFile = File(None),
    vehicle_image: UploadFile = File(None),
    vehicle_insurance_image: UploadFile = File(None),

    # -------- Common deps --------
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Combined API to:
    - Update vehicle details
    - Update license & vehicle documents (optional)
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)

    response = await DriverService().update_driver_vehicle_and_docs_service(
        request=request,
        db=db,
        body=body,
        files={
            "license_front_image": license_front_image,
            "license_back_image": license_back_image,
            "rc_image": rc_image,
            "vehicle_image": vehicle_image,
            "vehicle_insurance_image": vehicle_insurance_image,
        },
        current_user=current_user,
    )
    return response

@driverrouter.get("/vehicle_details")
async def get_driver_vehicle_details_api(
    request: Request,
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Retrieves the vehicle details for the driver.

    Args:
        request (Request): The request object.
        body (DriverVehicleDetailsSchema): The request body containing vehicle details.
        authrouter (HTTPAuthorizationCredentials): The authorization credentials.
        db (AsyncSession): The database session.

    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await GetDriverService().get_driver_vehicle_service(db, current_user)
    return response

@driverrouter.post("/select_plan")
async def select_plan_api(
    request: Request,
    plan_name: attribute.PlanNameEnum,
    db: AsyncSession = Depends(getdb),
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Selects a plan for the driver.
    Args:
        request (Request): The request object.
        db (AsyncSession): The database session.
        authrorize (HTTPAuthorizationCredentials): The authorization credentials.

    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await DriverPlanService().select_driver_plan(current_user, plan_name, db)
    return response


@driverrouter.post("/status/update")
async def update_driver_status_api(
    request: Request,
    body : LocationSchema,
    db: AsyncSession = Depends(getdb),
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Updates the driver's status.

    Args:
        request (Request): The request object.
        driver_status (int): The new status of the driver.
        db (AsyncSession): The database session.
        authrorize (HTTPAuthorizationCredentials): The authorization credentials.

    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await UpdateDriverStatusService().update_driver_status_service(
        current_user, db, body
    )
    return response

@driverrouter.get("/status")
async def fetch_driver_status_api(
    request: Request,
    db: AsyncSession = Depends(getdb),
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Fetches the driver's status.

    Args:
        request (Request): The request object.
        db (AsyncSession): The database session.
        authrorize (HTTPAuthorizationCredentials): The authorization credentials.

    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await DriverService().get_driver_status(
        db, current_user
    )
    return response

@driverrouter.get("/check/plan_expiry")
async def check_plan_expiry_api(
    db: AsyncSession = Depends(getdb)
):
    """
    Checks the driver's plan expiry status.

    Args:
        request (Request): The request object.
        db (AsyncSession): The database session.
        authrorize (HTTPAuthorizationCredentials): The authorization credentials.

    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await DriverPlanService().check_driver_plan_expiry_service(db)
    return response

@driverrouter.post("/my_rides")
async def driver_my_rides_api(
    body: schema.MyRidesSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """
    Endpoint to fetch the ride details of customer.
    Args:
         db (AsyncSession): The database session.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await RideDetailService().fetch_driver_rides_service(
        db, current_user, body.dict()
    )
    return response

@driverrouter.get("/list")
async def drivers_list_api(
    db: AsyncSession = Depends(getdb),
    page: int = Query(1, ge=1),
    search: str | None = Query(None),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """API endpoint to fetch the drivers list"""

    current_user = JWTOAuth2().verify_access_token(authorize.credentials)

    response = await GetDriverService().fetch_drivers_list_service(
        db,
        current_user,
        page,
        search
    )
    return response

@driverrouter.post("/approve/reject")
async def driver_approve_reject_api_by_admin(
    body: schema.DriverStatusSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """API endpoint to fetch the drivers list"""

    current_user = JWTOAuth2().verify_access_token(authorize.credentials)

    response = await GetDriverService().driver_approve_reject_by_admin_service(
        db,
        current_user,
        body.dict()
    )
    return response

@driverrouter.post("/submit_review")
async def review_api(
    body: schema.ReviewSchema,
    authrouter: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """This API is used to update the review for the user/customer
    Args:
        body (ReviewSchema): The request body containing review details.
        authrouter (HTTPAuthorizationCredentials): The authorization credentials.
        db (AsyncSession): The database session.
    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = JWTOAuth2().verify_access_token(authrouter.credentials)
    response = await UserProfileService().submit_review_service(
        db, current_user, body.dict()
    )
    return response
