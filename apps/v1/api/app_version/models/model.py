"""SQLAlchemy model for app force-update version config."""

from sqlalchemy import Boolean, Column, Enum, Integer, String, Text, UniqueConstraint

from apps.v1.api.app_version.models.attribute import AppTypeEnum, PlatformEnum
from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class AppVersionConfig(TimestampMixin, Base):
    """
    Stores min / latest app versions per app type and platform.

    Frontend compares local version against these values on Splash.
    """

    __tablename__ = "app_version_config"
    __table_args__ = (
        UniqueConstraint(
            "app_type",
            "platform",
            name="uq_app_version_config_app_type_platform",
        ),
    )

    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        autoincrement=constant.STATUS_TRUE,
    )
    app_type = Column(
        Enum(AppTypeEnum),
        nullable=constant.STATUS_FALSE,
        doc="customer or driver app",
    )
    platform = Column(
        Enum(PlatformEnum),
        nullable=constant.STATUS_FALSE,
        doc="android or ios",
    )
    min_supported_version = Column(
        String(20),
        nullable=constant.STATUS_FALSE,
        doc="Force update if client version is below this (semver)",
    )
    latest_version = Column(
        String(20),
        nullable=constant.STATUS_FALSE,
        doc="Optional soft-update prompt if below this (semver)",
    )
    force_update = Column(
        Boolean,
        default=constant.STATUS_FALSE,
        nullable=constant.STATUS_FALSE,
        doc="Emergency flag to force update regardless of version",
    )
    message = Column(
        Text,
        nullable=constant.STATUS_TRUE,
        doc="Message shown on update screen",
    )
    store_url = Column(
        String(500),
        nullable=constant.STATUS_TRUE,
        doc="Play Store / App Store URL",
    )
    is_active = Column(
        Boolean,
        default=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        doc="Whether this config row is active",
    )
