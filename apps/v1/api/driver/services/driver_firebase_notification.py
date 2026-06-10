"""Scheduler for checking driver plan expiration and sending notifications."""

import logging
from typing import List, Dict, Optional

import firebase_admin
from firebase_admin import credentials, messaging
from fastapi import status
from config import env_config

from apps.v1.api.base_service import BaseResponseService
from core.utils.message_variable import ErrorMessage, InfoMessage

logger = logging.getLogger(__name__)


class DriverFirebaseNotification(BaseResponseService):
    """Handles Firebase notifications for drivers."""

    _firebase_initialized: bool = False

    async def _initialize_firebase(self, user_type: str = None) -> bool:
        """Initialize Firebase app if not already ini   tialized."""
        try:
            # Firebase-safe check
            if not firebase_admin._apps:
                cred = credentials.Certificate("kubercab-3b5b5-bbd843c5a200.json")
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
        data: Optional[Dict] = None,
    ) -> bool:
        """
        Send a push notification to a single device token.

        Returns:
            bool: True when FCM accepted the message, False otherwise.
        """
        user_type = data.get("user_type") if data else None
        if not await self._initialize_firebase(user_type):
            return False
        try:
            message = self._build_message(device_token, title, body, data)
            messaging.send(message)
            logger.info("FCM notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {str(e)}")
            return False
