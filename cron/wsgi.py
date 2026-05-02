"""This module is responsible for Flask application setup and configuration."""

import env_config
from dotenv import load_dotenv
from driver_expiry_check import crop_app

load_dotenv()

# Run the Flask application
if __name__ == "__main__":
    #TODO: uncomment the below when plans are ready for the driver.
    # setup_driver_expiry_cron()
    crop_app.run(
        host=env_config.SOCKET_SERVER_HOST,
        port=env_config.SOCKET_SERVER_PORT,)
