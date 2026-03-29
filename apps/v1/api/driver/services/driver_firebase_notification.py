"""Scheduler for checking driver plan expiration and sending notifications."""

import logging
from typing import List, Dict, Optional

import firebase_admin
from firebase_admin import credentials, messaging
from fastapi import status

from apps.v1.api.base_service import BaseResponseService
from core.utils.message_variable import ErrorMessage, InfoMessage

logger = logging.getLogger(__name__)


class DriverFirebaseNotification(BaseResponseService):
    """Handles Firebase notifications for drivers."""

    _firebase_initialized: bool = False

    async def _initialize_firebase(self) -> bool:
        """Initialize Firebase app if not already initialized."""
        try:
            # Firebase-safe check
            if not firebase_admin._apps:
                cred = credentials.Certificate("kubercab-730b1e547e.json")
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized successfully.")
            return True

        except Exception as e:
            logger.error(f"Firebase initialization failed: {str(e)}")
            return False

    def _build_message(self, token: str, title: str, body: str, data: Optional[Dict] = None) -> messaging.Message:
        """Builds the Firebase notification message."""
        return messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=token
        )

    async def send_notification_to_drivers(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ):
        """
        Send ride notifications to nearby drivers.

        Args:
            drivers: List of dicts with keys: 'device_token' and 'driver_id'.
            title: Title of the notification.
            body: Body of the notification.
            data: Optional extra payload.
        """
        if not await self._initialize_firebase():
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain
            )
        logger.info("*************Hello******")
        try:
            message = self._build_message(device_token, title, body, data)
            messaging.send(message)
            print("Notification sent successfully")
            logger.info(f"Notification sent to driver.")
        except Exception as e:
            logger.error(f"Failed to send notification to driver : {str(e)}")

        return self.response(status.HTTP_200_OK, InfoMessage.notificationSentToDrivers)
