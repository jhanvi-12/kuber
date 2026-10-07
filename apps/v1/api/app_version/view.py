"""API endpoints for app version force-update config."""

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.app_version import schema
from apps.v1.api.app_version.models.attribute import AppTypeEnum, PlatformEnum
from apps.v1.api.app_version.services.app_version_service import AppVersionService
from apps.v1.api.pagination_service import oauth2
from config import db_config
from core.utils.token_authentication import JWTOAuth2

appversionrouter = APIRouter()
getdb = db_config.get_db


@appversionrouter.get("/version")
async def get_app_version_api(
    app_type: Optional[AppTypeEnum] = None,
    platform: Optional[PlatformEnum] = None,
    db: AsyncSession = Depends(getdb),
):
    """
    Public API for Splash: fetch min/latest version config.

    Query examples:
      GET /v1/app/version?app_type=customer&platform=android
      GET /v1/app/version   (all active configs)
    """
    response = await AppVersionService().get_version_service(
        db,
        app_type.value if app_type else None,
        platform.value if platform else None,
    )
    return response


@appversionrouter.post("/version")
async def update_app_version_api(
    body: schema.UpdateAppVersionSchema,
    db: AsyncSession = Depends(getdb),
    authorize: HTTPAuthorizationCredentials = Depends(oauth2),
):
    """Admin-only API to create or update version config for an app + platform."""
    current_user = JWTOAuth2().verify_access_token(authorize.credentials)
    response = await AppVersionService().update_version_service(
        db, current_user, body
    )
    return response
