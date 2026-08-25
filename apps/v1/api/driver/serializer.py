"""This module is responsible for the driver vehicle serializer."""

from marshmallow import Schema, fields


class DriverVehicleDocumentSchema(Schema):
    """This class is used to serialize the driver vehicle document."""
    # Driver Fields
    id = fields.Int()
    full_name = fields.Str()
    email = fields.Str()
    mobile = fields.Str()
    license_number = fields.Str()
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)
    # license_expiry_date = fields.DateTime()
    license_front_image = fields.Str()
    license_back_image = fields.Str()
    rc_image = fields.Str()

    # Vehicle Fields
    vehicle_id = fields.Int(attribute="vehicle.id")
    plate_number = fields.Str(attribute="vehicle.plate_number")
    ride_type = fields.Str(attribute="vehicle.ride_type")
    vehicle_type = fields.Str(attribute="vehicle.vehicle_type")
    vehicle_model = fields.Str(attribute="vehicle.vehicle_model")
    make = fields.Str(attribute="vehicle.make")
    vehicle_image = fields.Str(attribute="vehicle.vehicle_image")
    vehicle_insurance_image = fields.Str(attribute="vehicle.vehicle_insurance_image")
    # vehicle_insurance_expiration_date = fields.DateTime(attribute="vehicle.vehicle_insurance_expiration_date")


class DriverDetailDocsSchema(Schema):
    """This class is used to serialize the driver vehicle document."""
    # Driver Fields
    id = fields.Int()
    full_name = fields.Str()
    email = fields.Str()
    mobile = fields.Str()
    license_front_image = fields.Str()
    license_back_image = fields.Str()
    rc_image = fields.Str()

    # Vehicle Fields
    ride_type = fields.Str()
    vehicle_type = fields.Str()
    vehicle_image = fields.Str()
    vehicle_insurance_image = fields.Str()
