from datetime import datetime

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from config import db_session
from core.utils import constant_variable
getdb = db_session.session_factory()


class DataBaseMethod:
    """This class is provide the database methods"""

    def __init__(self, model):
        self.model = model

    async def save(self, validate_data, db: AsyncSession = Depends(getdb)):
        """This function creates a new object asynchronously.

        Arguments:
            self(db): database session
            validate_data (dict): validated data to be saved

        Returns:
            Returns the status of the operation (True/False).
        """
        try:
            db.add(validate_data)  # Add the object to the session
            await db.flush()  # Asynchronously flush the changes to the database
            return constant_variable.STATUS_TRUE
        except Exception as err:
            print(err)
            # Rollback is handled automatically when the transaction is not committed.
            return constant_variable.STATUS_FALSE

    async def save_all(self, validate_data: list, db: AsyncSession = Depends(getdb)):
        """Saves bulk data in the database."""
        try:
            db.add_all(validate_data)
            await db.commit()
            await db.flush()
            return constant_variable.STATUS_TRUE
        except Exception as err:
            print(err)
            db.rollback()
            db.close()
            return constant_variable.STATUS_FALSE

    async def bulk_insert_mapping(
        self, validate_data: dict, db: AsyncSession = Depends(getdb)
    ):
        """Saves bulk data in the database with its mapping"""
        try:
            db.bulk_insert_mappings(self.model, validate_data)
            await db.commit()
            await db.flush()
            return constant_variable.STATUS_TRUE
        except Exception as err:
            print(err)
            db.rollback()
            db.close()
            return constant_variable.STATUS_FALSE

    async def destroy(self, instance: object, db: AsyncSession = Depends(getdb)):
        """This function take a ID and destroy the object

        Arguments:
            self(db): database session
            models (object): models
            uuid (str): Object ID

        Returns:
            Returns the successfull API basic response format.
        """
        try:
            instance.deleted_at = datetime.utcnow()
            db.add(instance)
            await db.flush()
            return constant_variable.STATUS_TRUE
        except Exception as e:
            return constant_variable.STATUS_FALSE

    async def count(self, db: AsyncSession, filters: dict = None):
        """This function counts the number of records in the database based on the provided filters.

        Arguments:
            db (AsyncSession): The database session.
            filters (dict, optional): A dictionary of filters to apply to the count query. Defaults to None.
            column (str, optional): The specific column to count. If None, counts all records. Defaults to None.
        Returns:
            int: The count of records matching the filters.
        """
        try:
            stmt = select(func.count()).select_from(self.model)

            if filters:
                for key, value in filters.items():
                    stmt = stmt.where(getattr(self.model, key) == value)

            result = await db.execute(stmt)
            return result.scalar() or 0

        except Exception as e:
            print(f"Error in count method: {str(e)}")
            return 0

    async def sum(self, db: AsyncSession, column: str, filters: dict = None):
        """Sum a specific column with optional filters.

        Arguments:
            db (AsyncSession): The database session.
            column (str): The column to sum.
            filters (dict, optional): A dictionary of filters. Defaults to None.
        Returns:
            float: The sum of the column values.
        """
        try:
            stmt = select(func.sum(getattr(self.model, column))).select_from(self.model)

            if filters:
                for key, value in filters.items():
                    stmt = stmt.where(getattr(self.model, key) == value)

            result = await db.execute(stmt)
            return result.scalar() or 0.0

        except Exception as e:
            print(f"Error in sum method: {str(e)}")
            return 0.0