"""Service for reading and updating app version force-update config."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.app_version.models.method import AppVersionMethod
from apps.v1.api.app_version.models.model import AppVersionConfig
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import Admin
from apps.v1.api.base_service import BaseResponseService
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from core.utils.message_variable import ErrorMessage, InfoMessage


class AppVersionService(BaseResponseService):
    """Handles GET (public) and POST (admin) for app version config."""

    def _serialize_config(self, config: AppVersionConfig) -> dict:
        """Build FE-friendly payload; comparison happens on the client."""
        data = jsonable_encoder(config)
        # Prefer string values for enums in mobile clients
        data["app_type"] = (
            config.app_type.value
            if hasattr(config.app_type, "value")
            else config.app_type
        )
        data["platform"] = (
            config.platform.value
            if hasattr(config.platform, "value")
            else config.platform
        )
        return {
            "app_type": data["app_type"],
            "platform": data["platform"],
            "min_supported_version": data["min_supported_version"],
            "latest_version": data["latest_version"],
            "force_update": data["force_update"],
            "message": data.get("message"),
            "store_url": data.get("store_url"),
            "is_active": data.get("is_active", True),
        }

    async def get_version_service(
        self,
        db: AsyncSession,
        app_type: str = None,
        platform: str = None,
    ):
        """
        Public GET used on Splash.

        - With app_type + platform: return that single config.
        - Without filters: return all active configs (customer/driver x android/ios).
        """
        try:
            method = AppVersionMethod(AppVersionConfig)

            if app_type and platform:
                config = await method.find_by_app_type_and_platform(
                    db, app_type, platform
                )
                if not config:
                    return self.response(
                        status.HTTP_404_NOT_FOUND,
                        ErrorMessage.appVersionNotFound,
                    )
                return self.response(
                    status.HTTP_200_OK,
                    InfoMessage.appVersionRetrieved,
                    self._serialize_config(config),
                )

            configs = await method.find_all_active(db)
            if not configs:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.appVersionNotFound,
                )
            data = [self._serialize_config(item) for item in configs]
            return self.response(
                status.HTTP_200_OK,
                InfoMessage.appVersionRetrieved,
                data,
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def update_version_service(
        self,
        db: AsyncSession,
        current_user: dict,
        body,
    ):
        """Admin-only create or update version config for app_type + platform."""
        try:
            admin_id = current_user.get("user_id")
            admin_obj = await UserAuthMethod(Admin).find_by_id(db, admin_id)
            if not admin_obj or current_user.get("user_type") != constant.ROLE_ADMIN:
                return self.response(
                    status.HTTP_403_FORBIDDEN,
                    ErrorMessage.adminNotFound,
                )

            payload = body.dict()
            app_type = payload["app_type"]
            platform = payload["platform"]
            # Enum may come through as enum or str
            app_type_value = (
                app_type.value if hasattr(app_type, "value") else app_type
            )
            platform_value = (
                platform.value if hasattr(platform, "value") else platform
            )

            method = AppVersionMethod(AppVersionConfig)
            existing = await method.find_by_app_type_and_platform(
                db, app_type_value, platform_value, active_only=False
            )

            if existing:
                existing.min_supported_version = payload["min_supported_version"]
                existing.latest_version = payload["latest_version"]
                existing.force_update = payload.get(
                    "force_update", constant.STATUS_FALSE
                )
                existing.message = payload.get("message")
                existing.store_url = payload.get("store_url")
                existing.is_active = payload.get("is_active", constant.STATUS_TRUE)
                if not await DataBaseMethod(AppVersionConfig).save(existing, db):
                    return self.response(
                        status.HTTP_400_BAD_REQUEST,
                        ErrorMessage.appVersionUpdateFailed,
                    )
                await db.commit()
                return self.response(
                    status.HTTP_200_OK,
                    InfoMessage.appVersionUpdated,
                    self._serialize_config(existing),
                )

            new_config = AppVersionConfig(
                app_type=app_type_value,
                platform=platform_value,
                min_supported_version=payload["min_supported_version"],
                latest_version=payload["latest_version"],
                force_update=payload.get("force_update", constant.STATUS_FALSE),
                message=payload.get("message"),
                store_url=payload.get("store_url"),
                is_active=payload.get("is_active", constant.STATUS_TRUE),
            )
            if not await DataBaseMethod(AppVersionConfig).save(new_config, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.appVersionUpdateFailed,
                )
            await db.commit()
            return self.response(
                status.HTTP_201_CREATED,
                InfoMessage.appVersionUpdated,
                self._serialize_config(new_config),
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )
