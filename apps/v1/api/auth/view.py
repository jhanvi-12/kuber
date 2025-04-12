"""This module is responsible to contain API's endpoint"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
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
async def create_admin_api(
    request: Request,
    body: schema.CreateRegisterSchema,
    user_type: attribute.UserTypeEnum,
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
    response = await SignUpService().create_signup_service(request, db, user_type, body)
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


@authrouter.post("/forgot/password")
async def forgot_password_api(
    body: schema.ForgotPasswordSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(getdb),
):
    """
    Performs user password reset.

    Args:
        body (ForgotPasswordSchema): The request body containing reset password schema.
        db (AsyncSession): The database session.
        authorize (HTTPAuthorizationCredentials, optional): The authorization header containing JWT token. Defaults to Depends(oauth2).
    Returns:
        StandardResponse: The response object with status and message.
    """
    response = await ResetPasswordService().get_forgot_password_service(
        db, body.dict(), background_tasks
    )
    return response


@authrouter.post("/reset/password")
async def reset_password_api(
    body: schema.ResetPasswordSchema, db: AsyncSession = Depends(getdb)
):
    """Reset password for user.

    Args:
        body (schema.ResetPasswordSchema): The body containing reset password schema.
        db (AsyncSession, optional): database session Defaults to Depends(getdb).
    """
    response = await ResetPasswordService().get_reset_password_service(db, body)
    return response


@authrouter.post("/otp/verify")
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

@authrouter.put("/user/edit/profile")
async def get_edit_user_profile_api(
    request: Request,
    body: schema.EditProfileSchema,
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
    current_user = JWTOAuth2().verify_access_token(authrouter.credentials)
    response = await UserProfileService().get_edit_user_profile_service(
        request, db, body, current_user
    )
    return response
