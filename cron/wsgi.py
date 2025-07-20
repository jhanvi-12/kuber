"""This module is responsible for Flask application setup and configuration."""

from driver_expiry_check import crop_app

# Run the Flask application
if __name__ == "__main__":
    crop_app.run(
        host="localhost",
        port=5000)