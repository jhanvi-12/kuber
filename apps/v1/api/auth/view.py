"""This module is responsible to contain API's endpoint"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth import schema
from apps.v1.api.auth.models import attribute
from apps.v1.api.auth.services.login_service import LoginService
from apps.v1.api.auth.services.reset_pwd_service import ResetPasswordService
from apps.v1.api.auth.services.signup_service import SignUpService
from apps.v1.api.auth.services.user_profile_service import UserProfileService
from apps.v1.api.auth.services.verify_otp_service import VerifyOtpService
from apps.v1.api.pagination_service import oauth2
from config import db_config
from core.utils.token_authentication import JWTOAuth2

## Load API's
authrouter = APIRouter()
getdb = db_config.get_db


@authrouter.post("/register")
async def register_api(
    request: Request,
    full_name: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    mobile: str = Form(...),
    user_type: attribute.UserTypeEnum = Form(...),
    profile_image: UploadFile = File(None),
    db: AsyncSession = Depends(getdb),
):
    """
    Creates a new customer or driver user.

    Args:
        body (CreateRegisterSchema): The request body containing admin user details.
        db (AsyncSession): The database session.

    Returns:
        StandardResponse: The response object with status and message.
    """
    body = {
        "full_name": full_name,
        "email": email,
        "password": password,
        "mobile": mobile,
        "user_type": user_type,
    }
    response = await SignUpService().create_signup_service(
        request, db, user_type, body, profile_image
    )
    return response


@authrouter.post("/login")
async def login_api(body: schema.LoginSchema, db: AsyncSession = Depends(getdb)):
    """
    Performs user login.

    Args:
        body (LoginSchema): The request body containing login details.
        db (AsyncSession): The database session.

    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await LoginService().get_login_service(db, body)
    return response

@authrouter.post("/admin/login")
async def admin_login_api(body: schema.AdminLoginSchema, db: AsyncSession = Depends(getdb)):
    """
    Performs admin login.

    Args:
        body (LoginSchema): The request body containing admin login details.
        db (AsyncSession): The database session.

    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await LoginService().get_admin_login_service(db, body)
    return response

@authrouter.post("/device/register")
async def register_device_api(
    body: schema.DeviceTokenSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """This API route is used to generate device token for the user.

    Args:
        body (schema.DeviceTokenSchema): body which contains device token payload
        db (AsyncSession, optional): ).The database session.
        authorize (HTTPAuthorizationCredentials, optional): The authorization header 
        containing JWT token. Defaults to Depends(oauth2).
    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await LoginService().create_device_token(db, body, current_user)
    return response

# @authrouter.post("/logout")
# async def logout_api(
#     request: Request,
#     db: AsyncSession = Depends(getdb),
#     authorize: HTTPAuthorizationCredentials = Depends(oauth2),
# ):
#     """
#     Performs user logout.
#     """
#     user_id = request.state.user_id
#     session_id = authorize.credentials
#     response = await UserLogoutService().get_logout_service(db, user_id, session_id)
#     return response


@authrouter.post("/forgot_password")
async def forgot_password_api(
    body: schema.ForgotPasswordSchema,
    db: AsyncSession = Depends(getdb),
):
    """
    Performs user password reset.

    Args:
        body (ForgotPasswordSchema): The request body containing reset password schema.
        db (AsyncSession): The database session.
        authorize (HTTPAuthorizationCredentials, optional): The authorization header 
        containing JWT token. Defaults to Depends(oauth2).
    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await VerifyOtpService().request_otp_service(
        db, body
    )
    return response


@authrouter.post("/reset_password")
async def reset_password_api(
    body: schema.ResetPasswordSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """Reset password for user.

    Args:
        body (schema.ResetPasswordSchema): The body containing reset password schema.
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await ResetPasswordService().get_reset_password_service(
        db, body, current_user
    )
    return response

@authrouter.post("/otp_request")
async def request_otp_api(
    body: schema.RequestOtpSchema,
    db: AsyncSession = Depends(getdb),
):
    """
    Resend OTP API
    Args:
        body (ResendOtpSchema): The body containing resend OTP schema.
        background_tasks (BackgroundTasks): Background tasks for sending email.
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await VerifyOtpService().request_otp_service(
        db, body
    )
    return response

@authrouter.post("/otp_verify")
async def verify_otp_api(
    body: schema.VerifyOtpSchema, db: AsyncSession = Depends(getdb)
):
    """
    Verifies OTP for user.

    Args:
        body (VerifyOtpSchema): The body containing OTP verification schema.
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
    """
    response = await VerifyOtpService().verify_otp_service(db, body)
    return response


@authrouter.get("/user/profile")
async def get_user_profile_api(
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """
    User profile API
    Args:
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
        authorize (HTTPAuthorizationCredentials, optional): The authorization header
        containing JWT token. Defaults to Depends(oauth2).
    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await UserProfileService().get_user_profile_service(db, current_user)
    return response


@authrouter.put("/user/edit_profile")
async def get_edit_user_profile_api(
    request: Request,
    full_name: str = Form(None),
    email: EmailStr = Form(None),
    profile_image: UploadFile = File(None),
    authrouter: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Resend OTP API
    Args:
        body (ResendOtpSchema): The body containing resend OTP schema.
        background_tasks (BackgroundTasks): Background tasks for sending email.
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    body = {
        "full_name": full_name,
        "email": email,
        "profile_image": profile_image,
    }
    response = await UserProfileService().get_edit_user_profile_service(
        request, db, body, current_user
    )
    return response


@authrouter.post("/change_number")
async def change_number_api(
    request: Request,
    body: schema.ChangeNumberSchema,
    authrouter: HTTPAuthorizationCredentials = Depends(oauth2),
    db: AsyncSession = Depends(getdb),
):
    """
    Change number API
    Args:
        request (Request): The request object.
        number (str): The new number to be set.
        authrouter (HTTPAuthorizationCredentials): The authorization credentials.
        db (AsyncSession): The database session.
    Returns:
        StandardResponse: The response object with status and message.
    """
    current_user = request.state.user_data
    response = await UserProfileService().change_user_number_service(
        db, current_user, body.model_dump()
    )
    return response
