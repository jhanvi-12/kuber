"""This module is responsible for the driver vehicle serializer."""

from marshmallow import Schema, fields
from config import aws_config
from core.utils import constant_variable as constant


class RideResponse(Schema):
    """
    Schema for ride response
    """

    id = fields.Int()
    ride_type = fields.Str()
    longitude = fields.Float()
    latitude = fields.Float()
    mobile = fields.String(required=True)

    full_name = fields.String(required=True)
    email = fields.Email(required=True)
    plate_number = fields.String(required=True)
    profile_image = fields.Url(required=False, allow_none=True)
    review = fields.Float(required=False, allow_none=True)


class RideSchema(Schema):
    """Schema for the driver ride"""

    id = fields.Int(required=True)
    status = fields.Str(required=True)
    ride_fare = fields.Float(required=True)
    pickup_address = fields.Str(required=True)
    destination_address = fields.Str(required=True)
    driver_id = fields.Int(required=True)


class DriverRidesResponseSchema(Schema):
    """Schema for the driver rides"""

    rides = fields.List(fields.Nested(RideSchema), required=True)
    total_trips = fields.Int(required=True)


class CustomerRidesResSchema(Schema):
    """Schema for the customer rides"""

    rides = fields.List(fields.Nested(RideSchema), required=True)


class DriverListSchema(Schema):
    """Drivers list schema"""
    id = fields.Int(required=True)
    full_name = fields.Str(required=True)
    email = fields.Str(required=True)
    mobile = fields.Str(required=True)
    created_at = fields.DateTime(required=True)
    profile_image = fields.Method("get_profile_image")
    is_docs_verified = fields.Int(required=True)

    def get_profile_image(self, obj):
        """method to fetch the user profile"""
        image = (
            f"{aws_config.AWS_BASE_URL}{obj.profile_image}"
            if obj.profile_image is not constant.STATUS_NULL
            else constant.STATUS_NULL
        )
        return image

class DriverListResponseSchema(Schema):
    """Drivers list response schema."""
    drivers = fields.List(fields.Nested(DriverListSchema), required=True)
    total = fields.Int()
    page = fields.Int()
    limit = fields.Int()
