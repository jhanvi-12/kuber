"""This module is for swagger and request parameter schema of driver API's"""


from typing import Optional
from pydantic import BaseModel
from core.utils import constant_variable as constant
from fastapi import Form
from datetime import date

class DriverVehicleDetailsSchema(BaseModel):
    """This class is the driver vehicle details schema."""

    plate_number: str
    ride_type: str
    make: str
    vehicle_model: int

    class Config:
        """This class is the schema for vehicle configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "plate_number": "ABC1234",
                "ride_type": "Car/Auto/Bike",
                "make": "Toyota",
                "vehicle_model": 2023,
            }
        }

class DriverVehicleCombinedSchema(BaseModel):
    """This class is the driver vehicle details schema."""
    # -------- Vehicle details --------
    vehicle_type: str
    make: str
    vehicle_model: str
    vehicle_number: str

    # -------- License & insurance --------
    license_number: str
    license_expiration_date: date
    vehicle_insurance_expiration_date: date

    @classmethod
    def as_form(
        cls,
        vehicle_type: str = Form(...),
        make: str = Form(...),
        vehicle_model: str = Form(...),
        vehicle_number: str = Form(...),
        license_number: str = Form(...),
        license_expiration_date: date = Form(...),
        vehicle_insurance_expiration_date: date = Form(...),
    ):
        return cls(
            vehicle_type=vehicle_type,
            make=make,
            vehicle_model=vehicle_model,
            vehicle_number=vehicle_number,
            license_number=license_number,
            license_expiration_date=license_expiration_date,
            vehicle_insurance_expiration_date=vehicle_insurance_expiration_date,
        )

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

    class Config:
        """This class is the schema for plan configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "driver_id": 1,
                "status": 1
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
