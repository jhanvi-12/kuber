"""This module implements a cron job to check driver expiry dates."""

import asyncio
import logging
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import env_config
# from core.utils import constant_variable as constant
# from core.utils.helper import send_request
from flask import Flask

crop_app = Flask(__name__)
scheduler = BackgroundScheduler()
logger = logging.getLogger(__name__)

BASE_URL = env_config.BACKEND_URL
print(f"BASE_URL: {BASE_URL}")

def send_request(
    method: str, url: str, headers: dict = None, json_header: bool = False, data: dict = None
) -> requests.Response:
    """This function sends an HTTP request to the specified URL with the given method.
    Args:
        method (str): The HTTP method to use (e.g., GET, POST, PUT, DELETE).
        url (str): The URL to send the request to.
        json_header (bool): Whether to include a JSON content type header.
    Returns:
        requests.Response: The response object from the request.
    """
    try:
        default_headers = {"accept": "application/json"}
        if json_header and method.upper() in ["POST", "PUT", "PATCH"]:
            headers["Content-Type"] = "application/json"

        # Merge with custom headers
        if headers:
            default_headers.update(headers)

        response = requests.request(method, url, headers=default_headers, data=data)
        return response
    except Exception as e:
        print(f"Error sending request to {url}: {e}")
        return None


class SchedulerJob:
    """SchedulerJob class to manage the cron job for driver expiry check."""

    def check_driver_expiry():
        """
        Cron job to check driver expiry dates and update their status accordingly.
        Runs daily at midnight.
        """
        try:
            # Call the Baclend API to get the database session
            logger.info("Initiating driver expiry check...")
            route = f"{BASE_URL}driver/check/plan_expiry"
            if send_request("GET", route, json_header=True).status_code != 200:
                logger.error("Failed to connect to the backend API.")
                return False
            else:
                logger.info("Driver expiry check completed successfully.")
                return True
        except Exception as e:
            logger.error(f"Error in driver expiry check: {e}")


async def setup_driver_expiry_cron():
    """
    Setup the cron job for checking driver expiry dates.
    Runs every day at midnight (00:00).
    """
    # Add the cron job
    scheduler.add_job(
        SchedulerJob.check_driver_expiry,
        CronTrigger(
            day_of_week="mon-sun",
            hour=13,
            minute=25,
            timezone="Asia/Kolkata",
        ),
    )
    # Start the scheduler
    scheduler.start()

asyncio.run(setup_driver_expiry_cron())