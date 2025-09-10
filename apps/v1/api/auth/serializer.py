"""
This module defines the Marshmallow schema for serializing and deserializing user data.
"""

from marshmallow import Schema, fields

class RegisterResSchema(Schema):
    """
    Schema for serializing and deserializing user data.

    Attributes:
        id (int): Unique identifier for the user.
        name (str): Name of the user.
        email (str): Email address of the user.
        role_id (int): Role ID assigned to the user.
        contact (str): Contact number of the user.
        email_sent (bool): Indicates if the email was sent.
        created_at (datetime): Timestamp when the user was created.
        updated_at (datetime): Timestamp when the user was last updated.
    """
    id = fields.Int(required=True)
    full_name = fields.Str(required=True)
    email = fields.Email(required=True)
    mobile = fields.Str(required=True)
    profile_image = fields.Str(required=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)
    user_type = fields.Str(required=True)
