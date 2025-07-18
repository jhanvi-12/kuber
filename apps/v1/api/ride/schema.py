"""This module is responsible to contain ride schema definitions."""
from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional


class LocationSchema(BaseModel):
    """
    Schema for location coordinates and address
    """
    latitude: float = Field(..., description="Latitude coordinate of the location")
    longitude: float = Field(..., description="Longitude coordinate of the location")
    address: str = Field(..., description="Full address of the location")

    class Config:
        """
        Configuration for JSON schema generation
        """
        json_schema_extra = {
            "example": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "address": "Mumbai, Maharashtra, India"
            }
        }

class BookRideSchema(BaseModel):
    """
    Schema for booking a new ride
    """
    ride_fare: float = Field(..., description="Fare amount for the ride")
    source: LocationSchema = Field(..., description="Pickup location details")
    destination: LocationSchema = Field(..., description="Drop location details")
    ride_type: str = Field(..., description="Type of ride")

    class Config:
        """
        Configuration for JSON schema generation
        """
        json_schema_extra = {
            "example": {
                "ride_fare": 150.50,
                "source": {
                    "latitude": 19.0760,
                    "longitude": 72.8777,
                    "address": "Mumbai, Maharashtra, India"
                },
                "destination": {
                    "latitude": 19.2183,
                    "longitude": 72.9781,
                    "address": "Thane, Maharashtra, India"
                },
                "ride_type": "car/bike/auto"
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