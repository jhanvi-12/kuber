"""This module is for swagger and request parameter schema of driver API's"""


from typing import Optional
from pydantic import BaseModel
from core.utils import constant_variable as constant


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


