from app.models import (
    db, BinnedCodeDict, UserTicks, ClimberSummary, UserUpload, User, PerformancePyramid
)
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import os
from functools import wraps
import time
from sqlalchemy import desc, func, and_, exists, case, text
from sqlalchemy.orm import Query as BaseQuery
from uuid import UUID
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import logging
from .exceptions import DataProcessingError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
                    logger.warning(f"Database operation failed (attempt {retries}/{max_retries}): {str(e)}")
                    if retries == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for database operation")
                        raise
                    db.session.rollback()
                    time.sleep(delay * retries)  # Exponential backoff
                except SQLAlchemyError as e:
                    logger.error(f"Database error: {str(e)}", exc_info=True)
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
        """Save calculated data to database"""
        logger.info("Starting to save calculated data")
        
        try:
            # Use nested transaction if a transaction is already active
            with db.session.begin_nested():
                # Save UserTicks
                if 'user_ticks' in calculated_data:
                    logger.debug("Saving user ticks data")
                    DatabaseService._batch_save_dataframe(
                        calculated_data['user_ticks'], 
                        'user_ticks'
                    )
                
                # Reset sequences if using PostgreSQL
                if 'postgresql' in os.environ.get('DATABASE_URL', ''):
                    logger.debug("Resetting PostgreSQL sequences")
                    try:
                        db.session.execute(text("""
                            SELECT setval(pg_get_serial_sequence('user_ticks', 'id'), 
                                COALESCE((SELECT MAX(id) FROM user_ticks), 0) + 1, false);
                        """))
                    except Exception as e:
                        logger.warning(f"Failed to reset sequences: {str(e)}")
                        # Don't raise here, sequence reset is not critical
                
                # Save performance pyramid if present
                if 'performance_pyramid' in calculated_data:
                    logger.debug("Saving performance pyramid data")
                    DatabaseService._batch_save_dataframe(
                        calculated_data['performance_pyramid'],
                        'performance_pyramid'
                    )
                
                logger.info("Successfully saved all calculated data")
                
        except Exception as e:
            logger.error(f"Error saving calculated data: {str(e)}", exc_info=True)
            # Let the outer transaction handle the rollback if needed
            raise DataProcessingError(f"Failed to save data: {str(e)}")

    @staticmethod
    def _batch_save_dataframe(df: pd.DataFrame, table_name: str) -> None:
        """Save DataFrame to database in batches"""
        logger.debug(f"Starting batch save for {table_name}")
        
        # Get model class
        model_class = {
            'user_ticks': UserTicks,
            'performance_pyramid': PerformancePyramid
        }.get(table_name)
        
        if not model_class:
            raise ValueError(f"Invalid table name: {table_name}")
            
        # Get column names and types from model
        model_columns = {c.name: c.type for c in model_class.__table__.columns}
        
        try:
            # Prepare batch of records
            logger.debug("Preparing records for batch insert")
            records_to_insert = []
            
            # Prepare all records
            for idx, row in df.iterrows():
                data_dict = {k: v for k, v in row.where(pd.notnull(row), None).to_dict().items() 
                            if k in model_columns}
                
                # Handle UUID user_id
                if 'user_id' in data_dict:
                    user_id = data_dict['user_id']
                    if user_id is None:
                        logger.error(f"Null user_id found in row {idx}")
                        raise ValueError(f"user_id cannot be null (row {idx})")
                    
                    try:
                        # Handle different input types
                        if isinstance(user_id, UUID):
                            pass  # Already in correct format
                        elif isinstance(user_id, str):
                            data_dict['user_id'] = UUID(user_id.strip())
                        else:
                            data_dict['user_id'] = UUID(str(user_id).strip())
                    except (ValueError, AttributeError) as e:
                        logger.error(f"Invalid UUID format for user_id in row {idx}: {user_id}")
                        raise ValueError(f"Invalid UUID format for user_id in row {idx}: {user_id}")
                else:
                    logger.error(f"Missing user_id in row {idx}")
                    raise ValueError(f"user_id is required (missing in row {idx})")
                
                # Convert data types based on model column types
                for col, val in list(data_dict.items()):
                    col_type = model_columns[col]
                    try:
                        if isinstance(col_type, PostgresUUID) and not isinstance(val, UUID):
                            data_dict[col] = UUID(str(val).strip())
                        elif str(col_type) == 'INTEGER' and val is not None:
                            data_dict[col] = int(val)
                        elif str(col_type) == 'BOOLEAN' and val is not None:
                            data_dict[col] = bool(val)
                        elif str(col_type) == 'FLOAT' and val is not None:
                            data_dict[col] = float(val)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Type conversion error for column {col} in row {idx}: {val}")
                        raise ValueError(f"Type conversion error for column {col} in row {idx}: {val}")
                
                try:
                    records_to_insert.append(model_class(**data_dict))
                except TypeError as e:
                    logger.error(f"Error creating model instance for row {idx}: {e}")
                    raise ValueError(f"Error creating model instance for row {idx}: {e}")
            
            # Batch insert records
            logger.debug(f"Inserting {len(records_to_insert)} records")
            db.session.bulk_save_objects(records_to_insert)
            
            logger.info(f"Successfully saved {len(records_to_insert)} records to {table_name}")
            
        except Exception as e:
            logger.error(f"Error saving data to {table_name}: {str(e)}", exc_info=True)
            raise

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
    def get_user_ticks_by_id(user_id: int) -> List[UserTicks]:
        """Get all ticks for a user by user_id"""
        return UserTicks.query.filter_by(user_id=user_id).all()

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
        """Delete a tick and its associated performance pyramid entries"""
        try:
            # Get the tick to find its details
            user_tick = UserTicks.query.get(tick_id)
            if not user_tick:
                return False
                
            user_id = user_tick.user_id
            
            # Delete associated performance pyramid entries
            PerformancePyramid.query.filter_by(tick_id=tick_id).delete()
            
            # Delete the user tick
            db.session.delete(user_tick)
            db.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    @retry_on_db_error()
    def clear_user_data(user_id: int = None) -> None:
        """Clear all data for a user (ticks and performance pyramid) and reset sequences"""
        try:
            if user_id is None:
                raise ValueError("user_id must be provided")

            # Delete all related data in correct order
            PerformancePyramid.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            UserTicks.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            
            # Commit the deletions
            db.session.commit()
            
            # Add this to ensure complete data isolation
            ClimberSummary.query.filter_by(user_id=user_id).delete()
            UserUpload.query.filter_by(user_id=user_id).delete()
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_highest_grade(user_id: int, discipline: str) -> Optional[UserTicks]:
        return UserTicks.query.filter_by(
            user_id=user_id, 
            discipline=discipline
        ).order_by(desc(UserTicks.binned_code)).first()

    @staticmethod
    def get_discipline_counts(user_id: int) -> tuple:
        return db.session.query(
            UserTicks.discipline,
            func.count().label('count')
        ).filter_by(user_id=user_id).group_by(UserTicks.discipline).order_by(desc('count')).first()

    @staticmethod
    def get_earliest_tick_date(user_id: int) -> Optional[datetime]:
        return UserTicks.query.filter_by(user_id=user_id).order_by(UserTicks.tick_date).first()

    @staticmethod
    def get_preferred_crag(user_id: int, days: int = 365) -> tuple:
        date_threshold = datetime.now().date() - timedelta(days=days)
        return db.session.query(
            UserTicks.location,
            func.count().label('count')
        ).filter(
            UserTicks.user_id == user_id,
            UserTicks.tick_date >= date_threshold
        ).group_by(UserTicks.location).order_by(desc('count')).first()
    
    @staticmethod
    def get_clean_sends(user_id: int, discipline: str, style: list = None) -> BaseQuery:
        base_query = UserTicks.query.filter_by(
            user_id=user_id,
            send_bool=True,
            discipline=discipline
        )
        if style:
            base_query = base_query.filter(UserTicks.lead_style.in_(style))
        return base_query

    @staticmethod
    def get_max_clean_send(query: BaseQuery) -> Optional[UserTicks]:
        return query.order_by(desc(UserTicks.binned_code)).first()
    
    @staticmethod
    def get_recent_sends_count(user_id: int, days: int = 30) -> int:
        date_threshold = datetime.now() - timedelta(days=days)
        return UserTicks.query.filter(
            UserTicks.user_id == user_id,
            UserTicks.tick_date >= date_threshold,
            UserTicks.send_bool == True
        ).count()

    @staticmethod
    def get_current_projects(user_id: int, limit: int = 5) -> list:
        sent_routes = db.session.query(
            UserTicks.route_name,
            UserTicks.location
        ).filter(
            UserTicks.user_id == user_id,
            UserTicks.send_bool == True
        ).subquery()

        return db.session.query(
            UserTicks.route_name,
            UserTicks.location,
            UserTicks.discipline,
            UserTicks.route_grade,
            func.count(func.distinct(UserTicks.tick_date)).label('days_tried'),
            func.sum(
                case(
                    (UserTicks.length_category != 'multipitch', UserTicks.pitches),
                    else_=1
                )
            ).label('attempts'),
            func.max(UserTicks.tick_date).label('last_tried')
        ).filter(
            UserTicks.user_id == user_id,
            ~exists().where(and_(
                sent_routes.c.route_name == UserTicks.route_name,
                sent_routes.c.location == UserTicks.location
            ))
        ).group_by(
            UserTicks.route_name,
            UserTicks.location,
            UserTicks.discipline,
            UserTicks.route_grade
        ).having(
            func.count(func.distinct(UserTicks.tick_date)) >= 2
        ).order_by(
            desc(func.max(UserTicks.tick_date))
        ).limit(limit).all()

    @staticmethod
    def get_pyramids_by_user_id(user_id: UUID) -> Dict[str, List[Dict[str, Any]]]:
        """Get all pyramid data for a user by joining PerformancePyramid and UserTicks."""
        logger = logging.getLogger(__name__)
        logger.info(f"Fetching pyramid data for user {user_id}")
        
        try:
            # Query joining PerformancePyramid and UserTicks
            results = db.session.query(PerformancePyramid, UserTicks).join(
                UserTicks, PerformancePyramid.tick_id == UserTicks.id
            ).filter(PerformancePyramid.user_id == user_id).all()
            
            logger.info(f"Found {len(results)} total pyramid entries")

            # Initialize dictionaries for each discipline
            pyramids = {
                'sport': [],
                'trad': [],
                'boulder': []
            }

            # Process results
            for pyramid, tick in results:
                # Convert enum values to strings if they exist
                crux_energy = pyramid.crux_energy.value if pyramid.crux_energy else None
                crux_angle = pyramid.crux_angle.value if pyramid.crux_angle else None
                
                # Create combined data dictionary
                combined_data = {
                    'tick_id': pyramid.tick_id,
                    'send_date': pyramid.send_date,
                    'crux_energy': crux_energy,
                    'crux_angle': crux_angle,
                    'num_attempts': pyramid.num_attempts,
                    'days_tried': pyramid.days_attempts,
                    'description': pyramid.description,
                    'route_name': tick.route_name,
                    'route_grade': tick.route_grade,
                    'binned_grade': tick.binned_grade,
                    'binned_code': tick.binned_code,
                    'length': tick.length,
                    'length_category': tick.length_category,
                    'pitches': tick.pitches,
                    'location': tick.location,
                    'location_raw': tick.location_raw,
                    'lead_style': tick.lead_style,
                    'route_url': tick.route_url,
                    'route_stars': tick.route_stars,
                    'user_stars': tick.user_stars
                }

                # Add to appropriate discipline list
                discipline = tick.discipline.value if hasattr(tick.discipline, 'value') else tick.discipline
                if discipline in pyramids:
                    pyramids[discipline].append(combined_data)
                    logger.debug(f"Added entry for {discipline}: {tick.route_name} ({tick.route_grade})")

            # Sort each discipline's data and log counts
            for discipline in pyramids:
                pyramids[discipline].sort(key=lambda x: (-x['binned_code'], x['send_date']))
                logger.info(f"Processed {len(pyramids[discipline])} entries for {discipline}")

            return pyramids

        except Exception as e:
            logger.error(f"Error in get_pyramids_by_user_id: {str(e)}")
            raise