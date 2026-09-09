"""This module is responsible for loading environment configurations."""
import os
from os.path import join

from dotenv import load_dotenv

from .project_path import BASE_DIR

##### ENV configuration  #####
dotenv_path = join(BASE_DIR, ".env")
load_dotenv(dotenv_path)


## Database deatils ##
DATABASE_NAME = os.environ.get("DATABASE_NAME")
DATABASE_USER = os.environ.get("DATABASE_USER")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_PORT = os.environ.get("DATABASE_PORT")
BACKEND_URL = os.environ.get("BACKEND_URL")
SOCKET_SERVER_PORT = os.environ.get("SOCKET_SERVER_PORT")
SOCKET_SERVER_HOST = os.environ.get("SOCKET_SERVER_HOST")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
RESEND_EMAIL_HOST = os.environ.get("RESEND_EMAIL_HOST")
DRIVER_FIREBASE_JSON = os.environ.get("DRIVER_FIREBASE_JSON")
USER_FIREBASE_JSON = os.environ.get("USER_FIREBASE_JSON")
DISPATCH_MODE = os.environ.get("DISPATCH_MODE", "inline")  # queue | inline

## WKHTMLOPDF details ##
WKHTMLOPDF_PATH = os.environ.get("WKHTMLOPDF_PATH")
