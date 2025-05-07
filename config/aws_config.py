import os

from dotenv import load_dotenv

load_dotenv()

# Amazon s3 bucket credentials
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
EXPIRE_TIME = os.environ.get("EXPIRE_TIME")
REGION = os.environ.get("REGION")
LAMBDA_REGION = os.environ.get("LAMBDA_REGION")
PUBLIC_BUCKET = os.environ.get("PUBLIC_BUCKET")
AWS_BASE_URL = os.environ.get("AWS_BASE_URL")
PROXY_BASE_URL = os.environ.get("PROXY_BASE_URL")
AWS_USER_PROFILE_PATH = os.environ.get("AWS_USER_PROFILE_PATH")
AWS_DRIVER_PROFILE_PATH = os.environ.get("AWS_DRIVER_PROFILE_PATH")
S3_PATH_DRIVER_LICENSE_IMAGE = os.environ.get(
    "S3_PATH_DRIVER_LICENSE_IMAGE"
)
S3_PATH_DRIVER_VEHICLE_IMAGE = os.environ.get(
    "S3_PATH_DRIVER_VEHICLE_IMAGE"
)
S3_PATH_DRIVER_VEHICLE_INSURANCE_IMAGE = os.environ.get(
    "S3_PATH_DRIVER_VEHICLE_INSURANCE_IMAGE"
)

