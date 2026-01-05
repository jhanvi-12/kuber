"""This module is responsible to maintain the book ride service logic."""

import asyncio
import math
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.driver.services.driver_search_service import \
    DriverSearchService
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from core.redis_repo import RedisRideRepo
from core.utils import constant_variable as constant
from core.utils.message_variable import *


class BookRideService(BaseResponseService):
    """This class is used to define the book ride service methods."""

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great-circle distance between two points on the Earth using Haversine formula.
        Returns distance in kilometers.

        Args:
            lat1 (float): Latitude of first point
            lon1 (float): Longitude of first point
            lat2 (float): Latitude of second point
            lon2 (float): Longitude of second point

        Returns:
            float: Distance in kilometers
        """
        R = 6371  # Radius of the Earth in km
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    def calculate_distances_vectorized(
        self, source_lat: float, source_lon: float, drivers_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate distances between source and all drivers using vectorized operations.

        Args:
            source_lat (float): Source latitude
            source_lon (float): Source longitude
            drivers_df (pd.DataFrame): DataFrame containing driver locations

        Returns:
            pd.Series: Series containing distances for each driver
        """
        R = 6371  # Radius of the Earth in km

        # Convert to radians
        lat1_rad = np.radians(source_lat)
        lon1_rad = np.radians(source_lon)
        lat2_rad = np.radians(drivers_df["current_latitude"])
        lon2_rad = np.radians(drivers_df["current_longitude"])

        # Calculate differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        )
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        distances = R * c
        print("************", distances)
        return distances

    async def get_nearby_drivers(
        self,
        db: AsyncSession,
        source_lat: float,
        source_lon: float,
        ride_type: str,
        max_distance: float = constant.FLOAT_FIVE,
    ) -> List[Dict]:
        """
        Get all drivers within the specified distance range using pandas for faster processing.

        Args:
            db (AsyncSession): Database session
            source_lat (float): Source latitude
            source_lon (float): Source longitude
            max_distance (float): Maximum distance in kilometers (default: 5.0)

        Returns:
            List[Dict]: List of nearby drivers with their details
        """
        # Get all active drivers
        all_drivers = await DriverMethod(Driver).fecth_all_active_drivers_by_ride(db, ride_type)
        # Convert to DataFrame for faster processing
        drivers_data = [
            {
                "driver_id": driver.id,
                "current_latitude": driver.latitude,
                "current_longitude": driver.longitude,
                "device_token": driver.device_token,
            }
            for driver in all_drivers
        ]

        drivers_df = pd.DataFrame(drivers_data)

        if drivers_df.empty:
            return []

        # Calculate distances using vectorized operations
        drivers_df["distance"] = self.calculate_distances_vectorized(
            source_lat, source_lon, drivers_df
        )

        # Filter drivers within max_distance
        nearby_drivers_df = drivers_df[drivers_df["distance"] <= max_distance]

        # Convert back to list of dictionaries
        nearby_drivers = nearby_drivers_df.to_dict("records")

        return nearby_drivers

    async def create_book_ride_service(
        self, db: AsyncSession, body: dict, current_user: dict
    ):
        """
        Books a ride for the user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.
            current_user (dict): The current user's information.

        Returns:
            dict: A response indicating the success or failure of the ride booking.
        """
        try:
            body = body.dict()
            user_obj = await UserAuthMethod(User).find_by_id(
                db, current_user.get("user_id")
            )
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )
            # Create a new Ride object
            ride = Ride(
                user_id=current_user.get("user_id"),
                pickup_latitude=body.get("pickup_latitude"),
                pickup_longitude=body.get("pickup_longitude"),
                pickup_address=body.get("pickup_address"),
                destination_address=body.get("destination_address"),
                destination_latitude=body.get("destination_latitude"),
                destination_longitude=body.get("destination_longitude"),
                status=RideStatusEnum.FINDING_DRIVERS.value,
                ride_fare=body["ride_fare"],
                ride_type=body["ride_type"],
                ride_date=datetime.now(),
            )

            # Update the user address.
            user_obj.address = body["pickup_address"]

            # Add the ride to the database
            db.add(ride)
            db.add(user_obj)
            await db.commit()
            await db.refresh(ride)

            # INIT REDIS SEARCH STATE
            RedisRideRepo.init_search_state(ride.id, body.get("pickup_latitude"), body.get("pickup_longitude"))
            # Emit searching state
            await RideSocketEmitter.ride_searching(ride.id)

            # Start driver search ASYNC (background)
            asyncio.create_task(DriverSearchService.start_wave(
                ride.id,
                ride.ride_type,
                body.get("pickup_latitude"),
                body.get("pickup_longitude")
            ))
            data = jsonable_encoder(ride)

            return self.response(
                status.HTTP_200_OK, InfoMessage.findingDrivers, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
