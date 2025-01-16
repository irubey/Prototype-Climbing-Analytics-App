from app.models import (
    db, BinnedCodeDict, BoulderPyramid, SportPyramid, 
    TradPyramid, UserTicks
)
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import date
from app.services.pyramid_builder import PyramidBuilder
from sqlalchemy import text
import os
from functools import wraps
import time

def retry_on_db_error(max_retries=3, delay=1):
    """Decorator to retry database operations on connection errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    db.session.rollback()
                    time.sleep(delay * retries)  # Exponential backoff
                except SQLAlchemyError as e:
                    db.session.rollback()
                    raise
            return None
        return wrapper
    return decorator

class DatabaseService:
    """Handles all database CRUD operations"""

    @staticmethod
    @retry_on_db_error()
    def save_calculated_data(calculated_data: Dict[str, pd.DataFrame]) -> None:
        """Save calculated pyramid and tick data to database"""
        # Get userId from any of the dataframes
        userId = None
        for df in calculated_data.values():
            if not df.empty and 'userId' in df.columns:
                userId = int(df.iloc[0]['userId'])  # Explicitly convert to int
                break
        
        if userId is not None:
            # Clear existing data first
            DatabaseService.clear_user_data(userId=userId)
        else:
            raise ValueError("No userId found in calculated data")
        
        # Batch insert new data
        for table_name, df in calculated_data.items():
            if not df.empty:
                # Ensure userId is int in the DataFrame
                if 'userId' in df.columns:
                    df['userId'] = df['userId'].astype('int64').astype(int)
                DatabaseService._batch_save_dataframe(df, table_name)
        
        # Reset sequences if using PostgreSQL
        if 'postgresql' in os.environ.get('DATABASE_URL', ''):
            try:
                db.session.execute(text("""
                    SELECT setval(pg_get_serial_sequence('user_ticks', 'id'), 
                        COALESCE((SELECT MAX(id) FROM user_ticks), 0) + 1, false);
                    SELECT setval(pg_get_serial_sequence('sport_pyramid', 'id'), 
                        COALESCE((SELECT MAX(id) FROM sport_pyramid), 0) + 1, false);
                    SELECT setval(pg_get_serial_sequence('trad_pyramid', 'id'), 
                        COALESCE((SELECT MAX(id) FROM trad_pyramid), 0) + 1, false);
                    SELECT setval(pg_get_serial_sequence('boulder_pyramid', 'id'), 
                        COALESCE((SELECT MAX(id) FROM boulder_pyramid), 0) + 1, false);
                """))
                db.session.commit()
            except Exception as e:
                print(f"Warning: Failed to reset sequences: {e}")
                db.session.rollback()

    @staticmethod
    def _batch_save_dataframe(df: pd.DataFrame, table_name: str) -> None:
        """Batch save a dataframe to the appropriate database table"""
        model_class = {
            'sport_pyramid': SportPyramid,
            'trad_pyramid': TradPyramid,
            'boulder_pyramid': BoulderPyramid,
            'user_ticks': UserTicks
        }.get(table_name)
        
        if not model_class:
            raise ValueError(f"No model found for table name: {table_name}")

        model_columns = [c.name for c in model_class.__table__.columns]
        
        # Prepare batch of records
        records_to_insert = []
        
        # If this is a pyramid table, get all tick IDs in one query
        tick_ids = {}
        if table_name != 'user_ticks' and 'tick_id' not in df.columns:
            conditions = [(row['username'], row['route_name'], row['tick_date']) for _, row in df.iterrows()]
            if conditions:
                # Build one query to get all tick IDs
                tick_records = UserTicks.query.filter(
                    db.tuple_(
                        UserTicks.username,
                        UserTicks.route_name,
                        UserTicks.tick_date
                    ).in_(conditions)
                ).all()
                tick_ids = {(t.username, t.route_name, t.tick_date): t.id for t in tick_records}

        # Prepare all records
        for _, row in df.iterrows():
            data_dict = {k: v for k, v in row.where(pd.notnull(row), None).to_dict().items() 
                        if k in model_columns}
            
            # Ensure userId is int if present
            if 'userId' in data_dict:
                data_dict['userId'] = int(data_dict['userId'])
            
            # For pyramid tables, add the tick_id if not already present
            if table_name != 'user_ticks' and 'tick_id' not in data_dict:
                key = (data_dict['username'], data_dict['route_name'], data_dict['tick_date'])
                data_dict['tick_id'] = tick_ids.get(key)
            
            records_to_insert.append(model_class(**data_dict))

        # Bulk insert all records
        if records_to_insert:
            db.session.bulk_save_objects(records_to_insert)
            db.session.commit()

    @staticmethod
    def init_binned_code_dict(binned_code_dict: Dict[int, List[str]]) -> None:
        """Initialize the binned code dictionary in the database"""
        BinnedCodeDict.query.delete()
        db.session.commit()
        
        for code, grades in binned_code_dict.items():
            entry = BinnedCodeDict(binned_code=code, binned_grade=grades[0])
            db.session.add(entry)
        
        db.session.commit()

    @staticmethod
    @retry_on_db_error(max_retries=3)
    def get_user_ticks_by_id(userId: int) -> List[UserTicks]:
        """Get all ticks for a user by userId"""
        return UserTicks.query.filter_by(userId=userId).all()

    @staticmethod
    def update_user_tick(tick_id: int, **kwargs) -> Optional[UserTicks]:
        """Update a user tick"""
        try:
            user_tick = UserTicks.query.get(tick_id)
            if user_tick:
                for key, value in kwargs.items():
                    setattr(user_tick, key, value)
                db.session.commit()
            return user_tick
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_user_tick(tick_id: int) -> bool:
        """Delete a tick and its associated pyramid entries"""
        try:
            # Get the tick to find its details
            user_tick = UserTicks.query.get(tick_id)
            if not user_tick:
                return False
                
            userId = user_tick.userId
            
            # Delete the user tick
            db.session.delete(user_tick)
            db.session.commit()
            
            # Get remaining ticks for pyramid rebuild
            remaining_ticks = DatabaseService.get_user_ticks_by_id(userId)
            
            # Convert to DataFrame for pyramid building
            df = pd.DataFrame([r.as_dict() for r in remaining_ticks])
            
            # Build fresh pyramids from remaining ticks - no prediction needed
            pyramid_builder = PyramidBuilder()
            sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(df, db.session)
            
            # Clear existing pyramids and save new ones
            DatabaseService.clear_pyramids(userId=userId)
            DatabaseService.save_calculated_data({
                'sport_pyramid': sport_pyramid,
                'trad_pyramid': trad_pyramid,
                'boulder_pyramid': boulder_pyramid
            })
            
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    # Pyramid Operations
    @staticmethod
    @retry_on_db_error()
    def get_pyramids_by_user_id(userId: int) -> Dict[str, List[Any]]:
        """Get all pyramids for a user by userId"""
        return {
            'sport': SportPyramid.query.filter_by(userId=userId).order_by(SportPyramid.binned_code.desc()).all(),
            'trad': TradPyramid.query.filter_by(userId=userId).order_by(TradPyramid.binned_code.desc()).all(),
            'boulder': BoulderPyramid.query.filter_by(userId=userId).order_by(BoulderPyramid.binned_code.desc()).all()
        }

    @staticmethod
    def update_pyramid(discipline: str, pyramid_id: int, field: str, value: Any) -> bool:
        """Update a specific field in a pyramid"""
        try:
            model_class = {
                'sport': SportPyramid,
                'trad': TradPyramid,
                'boulder': BoulderPyramid
            }.get(discipline)
            
            if not model_class:
                return False
                
            record = model_class.query.get(pyramid_id)
            if record:
                setattr(record, field, value)
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_binned_code_dict() -> List[BinnedCodeDict]:
        """Get all binned code dictionary entries"""
        try:
            return BinnedCodeDict.query.all()
        except SQLAlchemyError as e:
            raise e

    @staticmethod
    def get_pyramid_by_id(discipline: str, pyramid_id: int) -> Optional[Union[SportPyramid, TradPyramid, BoulderPyramid]]:
        """Get a specific pyramid entry by ID"""
        try:
            model_class = {
                'sport': SportPyramid,
                'trad': TradPyramid,
                'boulder': BoulderPyramid
            }.get(discipline)
            
            if not model_class:
                return None
                
            return model_class.query.get(pyramid_id)
        except SQLAlchemyError as e:
            raise e

    @staticmethod
    def user_data_exists(userId: int = None) -> bool:
        """Check if user data exists in the database by userId"""
        try:
            # Build the filter conditions
            if userId is not None:
                user_filter = {'userId': userId}
            else:
                raise ValueError("userId must be provided")

            # Check for any user ticks
            has_ticks = db.session.query(UserTicks.query.filter_by(**user_filter).exists()).scalar()
            
            # Check for pyramids
            has_sport = db.session.query(SportPyramid.query.filter_by(**user_filter).exists()).scalar()
            has_trad = db.session.query(TradPyramid.query.filter_by(**user_filter).exists()).scalar()
            has_boulder = db.session.query(BoulderPyramid.query.filter_by(**user_filter).exists()).scalar()
            
            # Return True if user has ticks and at least one type of pyramid
            return has_ticks and (has_sport or has_trad or has_boulder)
        except SQLAlchemyError as e:
            raise e

    @staticmethod
    def clear_pyramids(userId: int = None) -> None:
        """Clear all pyramids for a user by userId"""
        try:
            if userId is not None:
                SportPyramid.query.filter_by(userId=userId).delete()
                TradPyramid.query.filter_by(userId=userId).delete()
                BoulderPyramid.query.filter_by(userId=userId).delete()
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    @retry_on_db_error()
    def clear_user_data(userId: int = None) -> None:
        """Clear all data for a user (ticks and pyramids) and reset sequences"""
        try:
            # Build the filter conditions
            if userId is not None:
                user_filter = {'userId': userId}
            else:
                raise ValueError("userId must be provided")

            # Delete all related data in correct order
            BoulderPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            SportPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            TradPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            UserTicks.query.filter_by(**user_filter).delete(synchronize_session=False)
            
            # Commit the deletions
            db.session.commit()
            
            # Reset sequences
            db.session.execute(text("""
                SELECT setval(pg_get_serial_sequence('user_ticks', 'id'), 
                    COALESCE((SELECT MAX(id) FROM user_ticks), 0) + 1, false);
                SELECT setval(pg_get_serial_sequence('sport_pyramid', 'id'), 
                    COALESCE((SELECT MAX(id) FROM sport_pyramid), 0) + 1, false);
                SELECT setval(pg_get_serial_sequence('trad_pyramid', 'id'), 
                    COALESCE((SELECT MAX(id) FROM trad_pyramid), 0) + 1, false);
                SELECT setval(pg_get_serial_sequence('boulder_pyramid', 'id'), 
                    COALESCE((SELECT MAX(id) FROM boulder_pyramid), 0) + 1, false);
            """))
            
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e  # Re-raise the exception after rollback