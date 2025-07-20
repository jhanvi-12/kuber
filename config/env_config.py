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


## WKHTMLOPDF details ##
WKHTMLOPDF_PATH = os.environ.get("WKHTMLOPDF_PATH")
