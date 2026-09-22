"""Request/response schemas for app version APIs."""

from typing import Optional

from pydantic import BaseModel, field_validator

from apps.v1.api.app_version.models.attribute import AppTypeEnum, PlatformEnum
from core.utils import constant_variable as constant

_SEMVER_PARTS = 3


def _validate_semver(value: str) -> str:
    """Ensure version looks like X.Y.Z with numeric parts."""
    parts = value.strip().split(".")
    if len(parts) != _SEMVER_PARTS:
        raise ValueError("Version must be in format X.Y.Z (e.g. 1.4.2)")
    if not all(part.isdigit() for part in parts):
        raise ValueError("Version parts must be numeric (e.g. 1.4.2)")
    return value.strip()


class UpdateAppVersionSchema(BaseModel):
    """Admin payload to create or update version config."""

    app_type: AppTypeEnum
    platform: PlatformEnum
    min_supported_version: str
    latest_version: str
    force_update: Optional[bool] = False
    message: Optional[str] = None
    store_url: Optional[str] = None
    is_active: Optional[bool] = True

    class Config:
        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "app_type": "customer",
                "platform": "android",
                "min_supported_version": "1.5.0",
                "latest_version": "1.6.0",
                "force_update": False,
                "message": "Please update the app to continue.",
                "store_url": "https://play.google.com/store/apps/details?id=com.kuber.customer",
                "is_active": True,
            }
        }

    @field_validator("min_supported_version", "latest_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        return _validate_semver(value)
