"""
This module defines a mixin class for adding timestamp fields to SQLAlchemy models.
The TimestampMixin class provides created_at, updated_at, and deleted_at fields
with automatic handling of default values and updates.

Classes:
    TimestampMixin: A mixin class that adds timestamp fields to SQLAlchemy models.
"""

from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from core.utils import DateTimeUtils, constant_variable


class TimestampMixin:
    """
    A mixin class that adds timestamp fields to SQLAlchemy models.

    Attributes:
        created_at (Mapped[datetime]): The datetime when the record was created.
        updated_at (Mapped[datetime]): The datetime when the record was last updated.
        deleted_at (Mapped[datetime]): The datetime when the record was deleted.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=DateTimeUtils.get_time,
        nullable=constant_variable.STATUS_FALSE,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=DateTimeUtils.get_time,
        onupdate=DateTimeUtils.get_time,
        nullable=constant_variable.STATUS_TRUE,
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=constant_variable.STATUS_TRUE,
    )

