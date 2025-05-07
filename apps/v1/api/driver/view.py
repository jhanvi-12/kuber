"""This module is responsible to contain driver API's endpoint"""

from fastapi import APIRouter, Depends, Request, File, Form, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.driver import schema
from apps.v1.api.auth.models import attribute
from apps.v1.api.driver.services.create_driver_vehicle_service import DriverService
from apps.v1.api.driver.services.get_driver_veh_service import GetDriverService
from apps.v1.api.pagination_service import oauth2
from config import db_config

driverrouter = APIRouter()
getdb = db_config.get_db


@driverrouter.post("/vehicle/details")
async def driver_vehicle_details_api(
    body: schema.DriverVehicleDetailsSchema,
    request: Request,
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Updates the vehicle details for the driver.
    
    Args:
        request (Request): The request object.
        body (DriverVehicleDetailsSchema): The request body containing vehicle details.
        authrouter (HTTPAuthorizationCredentials): The authorization credentials.
        db (AsyncSession): The database session.

    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await DriverService().create_driver_vehicle_service(
        db, body, current_user
    )
    return response

@driverrouter.get("/vehicle/details")
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
    response = await GetDriverService().get_driver_vehicle_service(
        db, current_user
    )
    return response

@driverrouter.post("/upload/vehicle/docs")
async def upload_driver_vehicle_docs(
    request: Request,
    db: AsyncSession = Depends(getdb),
    license_number: str = Form(...),
    license_expiration_date: str = Form(...),
    vehicle_insurance_expiration_date: str = Form(...),

    license_image: UploadFile = File(...),
    vehicle_image: UploadFile = File(...),
    vehicle_insurance_image: UploadFile = File(...),
    authrorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    Uploads driver license and vehicle documents with images.
    Args:
        request (Request): The request object.
        license_number (str): The driver's license number.
        license_expiration_date (str): The expiration date of the driver's license.
        vehicle_insurance_expiration_date (str): The expiration date of the vehicle insurance.
        license_image (UploadFile): The driver's license image file.
        vehicle_image (UploadFile): The vehicle image file.
        vehicle_insurance_image (UploadFile): The vehicle insurance image file.

    Returns:
        StandardResponse: The response object with status and message.
    """
    data = {
        "license_number": license_number,
        "license_expiration_date": license_expiration_date,
        "vehicle_insurance_expiration_date": vehicle_insurance_expiration_date,
        "license_image": license_image,
        "vehicle_image": vehicle_image,
        "vehicle_insurance_image": vehicle_insurance_image
    }
    current_user = request.state.user_data
    response = await DriverService().upload_driver_vehicle_docs(request, db, data, current_user)
    return response
