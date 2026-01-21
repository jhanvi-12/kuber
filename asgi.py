import os
import socketio
import click
import uvicorn
from socket_server import sio
from apps.server import app as fastapi_app
from config.env_config import load_dotenv
from core.utils import constant_variable

load_dotenv()

app = socketio.ASGIApp(
    sio,
    other_asgi_app=fastapi_app
)

@click.command()
@click.option(
    "--env",
    type=click.Choice(["local", "dev", "prod"], case_sensitive=False),
    default="local",
)
@click.option(
    "--debug",
    type=click.BOOL,
    is_flag=True,
    default=False,
)
def main(env: str, debug: bool):
    os.environ["ENV"] = env
    os.environ["DEBUG"] = str(debug)
    uvicorn.run(
        app="asgi:app",
        host=str(os.environ.get("SERVER_HOST", "localhost")),
        port=int(os.environ.get("SERVER_PORT", 8000)),
        reload=bool(os.environ.get("SERVER_DEBUG", constant_variable.STATUS_TRUE)),
        workers=1,
    )

# from socket_client import connect_socket
# @app.on_event("startup")
# async def startup_event():
#     await connect_socket()

if __name__ == "__main__":
    main()
