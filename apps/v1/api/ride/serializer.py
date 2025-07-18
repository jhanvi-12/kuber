"""This module is responsible for the driver vehicle serializer."""

from marshmallow import Schema, fields


class RideResponse(Schema):
    """
    Schema for ride response
    """
    id = fields.Int()
    driver_id = fields.Int()
    ride_type = fields.Str()
    ride_fare = fields.Float()
    source_longitude = fields.Float()
    destination_latitude = fields.Float()
    destination_address = fields.Str()
    ride_otp = fields.Int()
    user_id = fields.Int()
    status = fields.Str()
    source_latitude = fields.Float()
    source_address = fields.Str()
    destination_longitude = fields.Float()

