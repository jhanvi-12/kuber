"""This module is for swagger and request parameter schema of driver API's"""


from typing import Optional
from pydantic import BaseModel
from core.utils import constant_variable as constant
from fastapi import Form
from datetime import date

class DriverVehicleCombinedSchema(BaseModel):
    """This class is the driver vehicle details schema."""

    # -------- Vehicle details --------
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None

    # -------- License & insurance --------
    license_number: Optional[str] = None
    license_expiration_date: Optional[date] = None
    vehicle_insurance_expiration_date: Optional[date] = None
    is_docs_verified: Optional[int] = None

    @classmethod
    def as_form(
        cls,
        vehicle_type: Optional[str] = Form(None),
        make: Optional[str] = Form(None),
        vehicle_model: Optional[str] = Form(None),
        vehicle_number: Optional[str] = Form(None),
        license_number: Optional[str] = Form(None),
        license_expiration_date: Optional[date] = Form(None),
        vehicle_insurance_expiration_date: Optional[date] = Form(None),
        is_docs_verified: Optional[int] = Form(None),
    ):
        return cls(
            vehicle_type=vehicle_type,
            make=make,
            vehicle_model=vehicle_model,
            vehicle_number=vehicle_number,
            license_number=license_number,
            license_expiration_date=license_expiration_date,
            vehicle_insurance_expiration_date=vehicle_insurance_expiration_date,
            is_docs_verified=is_docs_verified,
        )

    def validate_for_create(self):
        """Call this in create service to ensure all fields are present."""
        required_fields = [
            "vehicle_type",
            "make",
            "vehicle_model",
            "vehicle_number",
            "license_number",
            "license_expiration_date",
            "vehicle_insurance_expiration_date",
            "is_docs_verified",
        ]
        missing = [f for f in required_fields if not getattr(self, f)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return True

class SelectPlanSchema(BaseModel):
    """This class is the select plan schema."""

    plan_name: str

    class Config:
        """This class is the schema for plan configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "plan_name": "Basic Plan",
            }
        }

class DriverStatusSchema(BaseModel):
    """class for updating the driver status"""
    driver_id : int
    status: int
    reason: Optional[str] = None

    class Config:
        """This class is the schema for plan configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "driver_id": 1,
                "status": 1,
                "reason": "Background verification completed successfully"
            }
        }


class MyRidesSchema(BaseModel):
    """Schema for the my rides"""
    start_date: str
    end_date: str

    class Config:
        """This class is the schema for plan configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "start_date": "2026-04-01T00:00:00",
                "end_date": "2026-04-05T23:59:59"
            }
        }
