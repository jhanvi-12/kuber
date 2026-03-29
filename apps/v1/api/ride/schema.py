"""This module is responsible to contain ride schema definitions."""
from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional


class LocationSchema(BaseModel):
    """
    Schema for location coordinates and address
    """
    status: int = Field(..., description="Status of the driver.")
    latitude: float = Field(..., description="Latitude coordinate of the location")
    longitude: float = Field(..., description="Longitude coordinate of the location")

    class Config:
        """
        Configuration for JSON schema generation
        """
        json_schema_extra = {
            "example": {
                "status": 1 or 0,
                "latitude": 19.0760,
                "longitude": 72.8777
            }
        }

class BookRideSchema(BaseModel):
    """
    Schema for booking a new ride
    """
    ride_fare: float = Field(..., description="Fare amount for the ride")
    pickup_latitude: float = Field(..., description="Pickup latitude of customer")
    pickup_longitude: float = Field(..., description="Pickup longitude of customer")
    pickup_address: str = Field(..., description="Pickup Address of customer")
    destination_latitude: float = Field(..., description="destinatio latitude of customer")
    destination_longitude: float = Field(..., description="destinatio longitude of customer")
    destination_address: str = Field(..., description="destinatio Address of customer")
    ride_type: str = Field(..., description="Type of ride")

    class Config:
        """
        Configuration for JSON schema generation
        """
        json_schema_extra = {
            "example": {
                "ride_fare": 150.50,
                "pickup_latitude": 19.0760,
                "pickup_longitude": 72.8777,
                "pickup_address": "Mumbai, Maharashtra, India",
                "destination_latitude": 19.2183,
                "destination_longitude": 72.9781,
                "destination_address": "Thane, Maharashtra, India",
                "ride_type": "car"
            }
        }

class UpdateRideStatus(BaseModel):
    """
    Schema for updating ride status
    """
    status: str = Field(..., description="New status of the ride")

    class Config:
        """
        Configuration for JSON schema generation
        """
        json_schema_extra = {
            "example": {
                "status": "COMPLETED"
            }
        }

class RideOTPShema(BaseModel):
    """Schema for ride otp"""
    otp: int
    ride_id: int

    class Config:
        json_schema_extra = {
            "example":{
                "otp": 1234,
                "ride_id": 3
            }
        }


class RideCancleSchema(BaseModel):
    """This class is used to cancel the ride with schema
    """
    class Config:
        """Config class"""
        json_schema_extra = {
            "user_type": "driver",
            "reason": "taking too long",
            "description": "Customer changed mind"
        }
