"""This module is responsible for the driver vehicle serializer."""

from marshmallow import Schema, fields


class RideResponse(Schema):
    """
    Schema for ride response
    """
    id = fields.Int()
    ride_type = fields.Str()
    longitude = fields.Float()
    latitude = fields.Float()
    mobile = fields.String(
        required=True
    )

    full_name = fields.String(required=True)
    email = fields.Email(required=True)
    plate_number = fields.String(required=True)
    profile_image = fields.Url(required=False, allow_none=True)
