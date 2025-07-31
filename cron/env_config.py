
import os
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL")
SOCKET_SERVER_HOST = os.environ.get("SOCKET_SERVER_HOST")
SOCKET_SERVER_PORT = os.environ.get("SOCKET_SERVER_PORT")