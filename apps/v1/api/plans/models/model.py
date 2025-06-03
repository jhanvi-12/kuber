"""This module is used to implement driver subscription plans functionality."""

from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class Plans(Base, TimestampMixin):
    """
    Plans table with fields: id, driver_id, plan_name, plan_days, expiry_date, 
    created_at, deleted_at, updated_at, is_expired, price.
    """

    __tablename__ = "plans"

    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        autoincrement=constant.STATUS_TRUE,
    )
    driver_id = Column(
        Integer,
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=constant.STATUS_FALSE,
        doc="Foreign key reference to drivers table"
    )
    plan_name = Column(
        String(100),
        nullable=constant.STATUS_FALSE,
        doc="Name of the subscription plan"
    )
    plan_days = Column(
        Integer,
        nullable=constant.STATUS_FALSE,
        doc="Duration of the plan in days"
    )
    expiry_date = Column(
        DateTime,
        nullable=constant.STATUS_FALSE,
        doc="Expiry date of the subscription plan"
    )
    price = Column(
        Float,
        nullable=constant.STATUS_FALSE,
        doc="Price of the subscription plan"
    )
    is_expired = Column(
        Boolean,
        default=constant.STATUS_FALSE,
        doc="Flag to indicate if the plan has expired"
    )
    # Relationship with Driver model
    driver = relationship("Driver", back_populates="plans") 