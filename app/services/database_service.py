from app.models import (
    db, BinnedCodeDict, BoulderPyramid, SportPyramid, 
    TradPyramid, UserTicks, ClimberSummary, UserUpload, User
)
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from app.services.pyramid_builder import PyramidBuilder
import os
from functools import wraps
import time
from sqlalchemy import desc, func, and_, exists, case, text
from sqlalchemy.orm import Query as BaseQuery

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
        # Save UserTicks FIRST
        if 'user_ticks' in calculated_data:
            DatabaseService._batch_save_dataframe(
                calculated_data['user_ticks'], 
                'user_ticks'
            )
        
        # Then save pyramids with valid foreign keys
        for table_name in ['sport_pyramid', 'trad_pyramid', 'boulder_pyramid']:
            if table_name in calculated_data:
                DatabaseService._batch_save_dataframe(
                    calculated_data[table_name], 
                    table_name
                )
        
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
        
        # Validate user_id exists
        if table_name in ['user_ticks', 'sport_pyramid', 'trad_pyramid', 'boulder_pyramid']:
            if 'user_id' not in df.columns:
                raise ValueError(f"Missing user_id column in {table_name} data")
            if df['user_id'].isnull().any():
                raise ValueError(f"Null user_id found in {table_name} data")
        
        if table_name == 'sport_pyramid' or table_name == 'trad_pyramid' or table_name == 'boulder_pyramid' and 'user_id' in df.columns:
            if df['user_id'].isnull().any():
                raise ValueError("Null user_id found in pyramid data")
        if table_name == 'climber_summary' and 'user_id' in df.columns:
            if df['user_id'].isnull().any():
                raise ValueError("Null user_id found in climber_summary data")
        
        # Validate foreign keys
        if table_name in ['sport_pyramid', 'trad_pyramid', 'boulder_pyramid']:
            if 'tick_id' not in df.columns:
                raise ValueError(f"Missing tick_id in {table_name} data")
            
            # Verify tick_ids exist in UserTicks
            existing_ticks = UserTicks.query.filter(
                UserTicks.id.in_(df['tick_id'].tolist())
            ).with_entities(UserTicks.id).all()
            
            existing_ids = {t.id for t in existing_ticks}
            missing = df[~df['tick_id'].isin(existing_ids)]
            if not missing.empty:
                raise ValueError(f"Invalid tick_ids found: {missing['tick_id'].tolist()}")
        
        # Prepare batch of records
        records_to_insert = []
        
        # If this is a pyramid table, get all tick IDs in one query
        tick_ids = {}
        if table_name != 'user_ticks' and 'tick_id' not in df.columns:
            conditions = [(row['user_id'], row['route_name'], row['tick_date']) for _, row in df.iterrows()]
            tick_records = UserTicks.query.filter(
                db.tuple_(
                    UserTicks.user_id,
                    UserTicks.route_name,
                    UserTicks.tick_date
                ).in_(conditions)
            ).all()
            tick_ids = {(t.user_id, t.route_name, t.tick_date): t.id for t in tick_records}

        # Prepare all records
        for _, row in df.iterrows():
            data_dict = {k: v for k, v in row.where(pd.notnull(row), None).to_dict().items() 
                        if k in model_columns}
            
            # Ensure user_id is int if present
            if 'user_id' in data_dict:
                data_dict['user_id'] = int(data_dict['user_id'])
            
            # For pyramid tables, add the tick_id if not already present
            if table_name != 'user_ticks' and 'tick_id' not in data_dict:
                key = (data_dict['user_id'], data_dict['route_name'], data_dict['tick_date'])
                data_dict['tick_id'] = tick_ids.get(key)
            
            records_to_insert.append(model_class(**data_dict))

        # Bulk insert all records
        if records_to_insert:
            db.session.bulk_save_objects(records_to_insert)
        
        # After bulk insert
        if 'postgresql' in os.environ.get('DATABASE_URL', ''):
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                f"COALESCE((SELECT MAX(id)+1 FROM {table_name}), 1), false)"
            ))

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
        """Delete a tick and its associated pyramid entries"""
        try:
            # Get the tick to find its details
            user_tick = UserTicks.query.get(tick_id)
            if not user_tick:
                return False
                
            user_id = user_tick.user_id
            
            # Delete the user tick
            db.session.delete(user_tick)
            db.session.commit()
            
            # Get remaining ticks for pyramid rebuild
            remaining_ticks = DatabaseService.get_user_ticks_by_id(user_id)
            
            # Convert to DataFrame for pyramid building
            df = pd.DataFrame([r.as_dict() for r in remaining_ticks])
            
            # Build fresh pyramids from remaining ticks - no prediction needed
            pyramid_builder = PyramidBuilder()
            sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(df, db.session)
            
            # Clear existing pyramids and save new ones
            DatabaseService.clear_pyramids(user_id=user_id)
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
    def get_pyramids_by_user_id(user_id: int) -> Dict[str, List[Any]]:
        """Get all pyramids for a user by user_id"""
        return {
            'sport': SportPyramid.query.filter_by(user_id=user_id).order_by(SportPyramid.binned_code.desc()).all(),
            'trad': TradPyramid.query.filter_by(user_id=user_id).order_by(TradPyramid.binned_code.desc()).all(),
            'boulder': BoulderPyramid.query.filter_by(user_id=user_id).order_by(BoulderPyramid.binned_code.desc()).all()
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
    def user_data_exists(user_id: int = None) -> bool:
        """Check if user data exists in the database by user_id"""
        try:
            # Build the filter conditions
            if user_id is not None:
                user_filter = {'user_id': user_id}
            else:
                raise ValueError("user_id must be provided")

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
    def clear_pyramids(user_id: int = None) -> None:
        """Clear all pyramids for a user by user_id"""
        try:
            if user_id is not None:
                SportPyramid.query.filter_by(user_id=user_id).delete()
                TradPyramid.query.filter_by(user_id=user_id).delete()
                BoulderPyramid.query.filter_by(user_id=user_id).delete()
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    @retry_on_db_error()
    def clear_user_data(user_id: int = None) -> None:
        """Clear all data for a user (ticks and pyramids) and reset sequences"""
        try:
            # Build the filter conditions
            if user_id is not None:
                user_filter = {'user_id': user_id}
            else:
                raise ValueError("user_id must be provided")

            # Delete all related data in correct order
            BoulderPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            SportPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            TradPyramid.query.filter_by(**user_filter).delete(synchronize_session=False)
            UserTicks.query.filter_by(**user_filter).delete(synchronize_session=False)
            
            # Commit the deletions
            db.session.commit()
            
            # Get current max ID safely
            max_id = db.session.query(func.max(User.id)).scalar() or 0
            new_start = max_id + 1 if max_id > 0 else 1
            
            # Reset sequence using PostgreSQL-specific command
            db.session.execute(text(
                f"ALTER SEQUENCE users_id_seq RESTART WITH {new_start};"
            ))
            
            db.session.commit()

            # Add this to ensure complete data isolation
            ClimberSummary.query.filter_by(user_id=user_id).delete()
            UserUpload.query.filter_by(user_id=user_id).delete()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e  # Re-raise the exception after rollback
        
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
    def get_style_analysis(user_id: int, model_class, style_column: str) -> list:
        return db.session.query(
            style_column,
            func.count().label('count'),
            func.max(model_class.binned_code).label('max_grade')
        ).filter_by(user_id=user_id).group_by(style_column).all()

    @staticmethod
    def get_combined_style_data(user_id: int, column: str) -> list:
        return db.session.query(
            getattr(SportPyramid, column),
            func.count().label('count')
        ).filter_by(user_id=user_id).union_all(
            db.session.query(getattr(TradPyramid, column), func.count())
            .filter_by(user_id=user_id)
        ).union_all(
            db.session.query(getattr(BoulderPyramid, column), func.count())
            .filter_by(user_id=user_id)
        ).group_by(getattr(SportPyramid, column)).all()
    
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
    def validate_pyramid_data(user_id: int):
        """Ensure all pyramid entries have valid user relationships"""
        # Check sport pyramid
        invalid_sport = db.session.query(SportPyramid).filter(
            SportPyramid.user_id == user_id,
            ~exists().where(UserTicks.id == SportPyramid.tick_id)
        ).first()
        if invalid_sport:
            raise IntegrityError(f"Invalid sport pyramid tick: {invalid_sport.tick_id}")

        # Similar checks for trad and boulder pyramids...