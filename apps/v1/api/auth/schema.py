"""This module is for swager and request parameter schema"""


from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from core.utils import constant_variable as constant
from core.utils.validation import ValidationMethods


class CreateRegisterSchema(BaseModel):
    """This class is the admin schema for creating a new admin"""

    full_name: str
    email: EmailStr
    password: str
    confirm_password: str
    mobile: str

    class Config:
        """This class is the schema for admin configuration."""

        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "full_name": "Jane Doe",
                "email": "abc123@example.com",
                "password": "Password@123",
                "confirm_password": "Password@123",
                "mobile": "1234567890"
            }
        }

class UpdateRegisterSchema(BaseModel):
    """
    Schema for updating an customer and driver.
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    mobile: Optional[str] = None

    class Config:
        """This class is the schema for admin update configuration."""
        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "full_name": "Jane Doe",
                "email": "abc123@example.com",
                "password": "Password@123",
                "mobile": "1234567890"
            }
        }

class LoginSchema(BaseModel):
    """This class represents the login schema.
    """
    email: EmailStr
    password: str

    class Config:
        """This class is the schema for user configuration."""
        from_attributes = constant.STATUS_TRUE
        extra = "forbid"
        json_schema_extra = {
            "example": {"email": "johnsmith@example.com", "password": "Abc@123"}
        }

    @field_validator("password")
    def password_validation(cls, v):
        return ValidationMethods().validate_password(v)

class ForgotPasswordSchema(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr

    model_config = ConfigDict(
        from_attributes=constant.STATUS_TRUE,
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "johnsmith@gmail.com",
            }
        },
    )

class VerifyOtpSchema(BaseModel):
    """This class is used to verify OTP."""
    email: EmailStr
    otp: int

    class Config:
        """This class is the schema for user configuration."""
        model_config = ConfigDict(
            from_attributes=constant.STATUS_TRUE,
            extra="forbid",
            json_schema_extra={
                "example": {
                    "email": "abc@example.com",
                    "otp": 1234,
                }
            }
        )

class ResetPasswordSchema(BaseModel):
    """This class is used to reset password."""
    old_password: str
    new_password: str
    confirm_password: str

    model_config = ConfigDict(
        from_attributes=constant.STATUS_TRUE,
        extra="forbid",
        json_schema_extra={
            "example": {
                "old_password": "password@123",
                "new_password": "Password@123",
                "confirm_password": "Password@123",
            }
        }
    )

class EditProfileSchema(BaseModel):
    """Schema for editing user profile."""
    profile_image: Optional[str] = constant.STATUS_NULL
    full_name: Optional[str] = constant.STATUS_NULL
    email: Optional[EmailStr] = constant.STATUS_NULL

    class Config:
        """Schema configuration."""
        extra = "forbid"
        from_attributes = constant.STATUS_TRUE
        json_schema_extra = {
            "example": {
                "profile_image": "base64 image",
                "full_name": "John Doe",
                "email": "john@gmail.com",
            }
        }
