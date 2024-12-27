from app.models import (
    db, BinnedCodeDict, BoulderPyramid, SportPyramid, 
    TradPyramid, UserTicks
)
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import date
from app.services.pyramid_builder import PyramidBuilder
from sqlalchemy import text

class DatabaseService:
    """Handles all database CRUD operations"""

    @staticmethod
    def save_calculated_data(calculated_data: Dict[str, pd.DataFrame]) -> None:
        """Save calculated pyramid and tick data to database"""
        try:
            # Start a new transaction
            db.session.begin_nested()
            
            # Get username from any of the dataframes
            username = None
            for df in calculated_data.values():
                if not df.empty and 'username' in df.columns:
                    username = df.iloc[0]['username']
                    break
            
            if username:
                # Clear existing data first
                DatabaseService.clear_user_data(username)
            
            # Save new data
            for table_name, df in calculated_data.items():
                DatabaseService._save_dataframe_to_table(df, table_name)
            
            # Commit the transaction
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _save_dataframe_to_table(df: pd.DataFrame, table_name: str) -> None:
        """Save a dataframe to the appropriate database table"""
        model_class = {
            'sport_pyramid': SportPyramid,
            'trad_pyramid': TradPyramid,
            'boulder_pyramid': BoulderPyramid,
            'user_ticks': UserTicks
        }.get(table_name)
        
        if not model_class:
            raise ValueError(f"No model found for table name: {table_name}")

        model_columns = [c.name for c in model_class.__table__.columns]

        # If this is a pyramid table and tick_id is not in the DataFrame,
        # we need to get the tick IDs from UserTicks
        if table_name != 'user_ticks' and 'tick_id' not in df.columns:
            # Get tick IDs for each route
            tick_ids = {}
            for _, row in df.iterrows():
                tick = UserTicks.query.filter_by(
                    username=row['username'],
                    route_name=row['route_name'],
                    tick_date=row['tick_date']
                ).first()
                if tick:
                    key = (row['username'], row['route_name'], row['tick_date'])
                    tick_ids[key] = tick.id

        for _, row in df.iterrows():
            data_dict = {k: v for k, v in row.where(pd.notnull(row), None).to_dict().items() 
                        if k in model_columns}
            
            # For pyramid tables, add the tick_id if not already present
            if table_name != 'user_ticks' and 'tick_id' not in data_dict:
                key = (data_dict['username'], data_dict['route_name'], data_dict['tick_date'])
                data_dict['tick_id'] = tick_ids.get(key)
                
            exists = db.session.query(model_class).filter_by(
                username=data_dict['username'],
                route_name=data_dict['route_name'], 
                tick_date=data_dict['tick_date']
            ).first()

            if not exists:
                new_entry = model_class(**data_dict)
                db.session.add(new_entry)

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

    # User Ticks Operations
    @staticmethod
    def get_user_ticks(username: str) -> List[UserTicks]:
        """Get all ticks for a user"""
        try:
            return UserTicks.query.filter_by(username=username).all()
        except SQLAlchemyError as e:
            raise e

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
                
            # Store info needed for pyramid deletion
            username = user_tick.username
            
            # Delete the user tick
            db.session.delete(user_tick)
            db.session.commit()  # Commit the tick deletion first
            
            # Get remaining ticks for pyramid rebuild
            remaining_ticks = DatabaseService.get_user_ticks(username)
            
            # Convert to DataFrame for pyramid building
            df = pd.DataFrame([r.as_dict() for r in remaining_ticks])
            
            # Build fresh pyramids from remaining ticks
            pyramid_builder = PyramidBuilder()
            sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(df)
            
            # Clear existing pyramids and save new ones
            DatabaseService.clear_pyramids(username)
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
    def get_pyramids_by_username(username: str) -> Dict[str, List[Any]]:
        """Get all pyramids for a user, sorted by difficulty (binned_code)"""
        try:
            return {
                'sport': SportPyramid.query.filter_by(username=username).order_by(SportPyramid.binned_code.desc()).all(),
                'trad': TradPyramid.query.filter_by(username=username).order_by(TradPyramid.binned_code.desc()).all(),
                'boulder': BoulderPyramid.query.filter_by(username=username).order_by(BoulderPyramid.binned_code.desc()).all()
            }
        except SQLAlchemyError as e:
            raise e

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
    def user_data_exists(username: str) -> bool:
        """Check if user data exists in the database"""
        try:
            # Check for any user ticks
            has_ticks = db.session.query(UserTicks.query.filter_by(username=username).exists()).scalar()
            
            # Check for pyramids
            has_sport = db.session.query(SportPyramid.query.filter_by(username=username).exists()).scalar()
            has_trad = db.session.query(TradPyramid.query.filter_by(username=username).exists()).scalar()
            has_boulder = db.session.query(BoulderPyramid.query.filter_by(username=username).exists()).scalar()
            
            # Return True if user has ticks and at least one type of pyramid
            return has_ticks and (has_sport or has_trad or has_boulder)
        except SQLAlchemyError as e:
            raise e

    @staticmethod
    def clear_pyramids(username: str) -> None:
        """Clear all pyramids for a user"""
        try:
            SportPyramid.query.filter_by(username=username).delete()
            TradPyramid.query.filter_by(username=username).delete()
            BoulderPyramid.query.filter_by(username=username).delete()
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def clear_user_data(username: str) -> None:
        """Clear all data for a user (ticks and pyramids) and reset sequences"""
        try:
            # Delete all related data in correct order
            BoulderPyramid.query.filter_by(username=username).delete(synchronize_session=False)
            SportPyramid.query.filter_by(username=username).delete(synchronize_session=False)
            TradPyramid.query.filter_by(username=username).delete(synchronize_session=False)
            UserTicks.query.filter_by(username=username).delete(synchronize_session=False)
            
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
            raise e