"""Enums for app version force-update config."""

from enum import Enum


class AppTypeEnum(str, Enum):
    """App type for version config (customer / driver apps)."""

    CUSTOMER = "customer"
    DRIVER = "driver"


class PlatformEnum(str, Enum):
    """Mobile platform."""

    ANDROID = "android"
    IOS = "ios"
