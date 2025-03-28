"""
Database service for logbook operations.

This module provides functionality for:
- Managing user ticks and performance data
- Handling tag operations
- Tracking sync status
- Bulk database operations
"""

from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator, Set
from uuid import UUID
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, date
import traceback
import pandas as pd

from app.core.logging import logger
from app.core.exceptions import DatabaseError
from app.models.enums import (
    LogbookType,
)
from app.models import (
    UserTicks,
    PerformancePyramid,
    Tag,
    User,
    UserTicksTags,
)
from app.db.session import get_db
from app.core.auth import get_password_hash

class DatabaseService:
    """Service for handling all database operations for the logbook service"""
    
    def __init__(self, session: AsyncSession):
        logger.info("Initializing DatabaseService")
        self.session = session
    
    @classmethod
    async def get_instance(cls) -> AsyncGenerator['DatabaseService', None]:
        """Get a new instance with a properly managed session"""
        logger.debug("Creating new DatabaseService instance")
        try:
            async for session in get_db():
                logger.debug("Database session acquired")
                yield cls(session)
        except Exception as e:
            logger.error("Error creating DatabaseService instance", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError("Failed to create database service instance")
    


    async def save_user_ticks(
        self,
        ticks_data: List[Dict[str, Any]],
        user_id: UUID
    ) -> List[UserTicks]:
        """Save user ticks to database, skipping existing records with same route_name and tick_date"""
        logger.info("Saving user ticks", extra={
            "user_id": str(user_id),
            "tick_count": len(ticks_data)
        })
        
        try:
            # Get existing ticks for this user
            stmt = select(UserTicks).where(
                UserTicks.user_id == user_id
            )
            result = await self.session.execute(stmt)
            existing_ticks = result.scalars().all()
            
            # Create a set of existing route_name + tick_date combinations
            existing_combinations = {
                (tick.route_name, tick.tick_date.isoformat() if tick.tick_date else None)
                for tick in existing_ticks
            }
            
            # Log detailed datetime information for existing ticks
            sample_existing = [(tick.route_name, tick.tick_date, 
                              type(tick.tick_date).__name__ if tick.tick_date else None,
                              tick.tick_date.isoformat() if tick.tick_date else None) 
                             for tick in existing_ticks[:3]]
            
            logger.info("Database deduplication datetime analysis", extra={
                "sample_existing_ticks": [{
                    "route_name": name,
                    "tick_date_raw": str(date),
                    "tick_date_type": type_,
                    "tick_date_iso": iso
                } for name, date, type_, iso in sample_existing],
                "existing_ticks_count": len(existing_ticks)
            })
            
            # Filter out ticks that already exist
            new_ticks_data = []
            skipped_count = 0
            duplicate_samples = []
            
            # Log sample of incoming tick dates
            sample_incoming = ticks_data[:3]
            logger.info("Database incoming tick date analysis", extra={
                "sample_incoming": [{
                    "route_name": tick.get('route_name'),
                    "tick_date_raw": str(tick.get('tick_date')),
                    "tick_date_type": type(tick.get('tick_date')).__name__,
                    "tick_date_iso": tick.get('tick_date').isoformat() if tick.get('tick_date') else None
                } for tick in sample_incoming]
            })
            
            for tick in ticks_data:
                tick_date = tick.get('tick_date')
                
                # Handle NaN values in tags
                if '_tags_list' in tick:
                    tags = tick['_tags_list']
                    if isinstance(tags, (list, pd.Series)):
                        # Keep only valid tags
                        tick['_tags_list'] = [tag for tag in tags if tag and not pd.isna(tag)]
                        if not tick['_tags_list']:  # If all tags were invalid, set to None
                            tick['_tags_list'] = None
                    elif pd.isna(tags):  # Single NaN value
                        tick['_tags_list'] = None
                
                # Ensure consistent datetime format
                if isinstance(tick_date, (date, datetime)):
                    tick_date = tick_date.isoformat()
                elif isinstance(tick_date, pd.Timestamp):
                    tick_date = tick_date.date().isoformat()
                elif isinstance(tick_date, str):
                    try:
                        tick_date = pd.to_datetime(tick_date, utc=True).date().isoformat()
                    except Exception as e:
                        logger.warning(f"Invalid tick_date format", extra={
                            "error": str(e),
                            "route_name": tick.get('route_name'),
                            "raw_tick_date": tick_date,
                            "tick_date_type": type(tick_date).__name__
                        })
                        continue
                
                combination = (tick.get('route_name'), tick_date)
                if combination not in existing_combinations:
                    new_ticks_data.append(tick)
                else:
                    skipped_count += 1
                    if len(duplicate_samples) < 3:
                        duplicate_samples.append({
                            "route_name": tick.get('route_name'),
                            "tick_date": tick_date,
                            "tick_date_type": type(tick_date).__name__
                        })
                    logger.debug("Skipping duplicate tick", extra={
                        "route_name": tick.get('route_name'),
                        "tick_date": tick_date,
                        "combination": str(combination)
                    })
            
            logger.info("Database deduplication results", extra={
                "total_ticks": len(ticks_data),
                "new_ticks": len(new_ticks_data),
                "skipped_ticks": skipped_count,
                "sample_duplicates": duplicate_samples,
                "example_combinations": str(list(existing_combinations)[:3]) if existing_combinations else "None"
            })
            
            if not new_ticks_data:
                logger.info("No new ticks to save")
                return []
            
            # Create UserTicks objects for new ticks
            tick_objects = []
            for tick in new_ticks_data:
                # Extract tags_list before creating UserTicks object
                tags_list = tick.pop('_tags_list', None) if '_tags_list' in tick else None
                
                if 'discipline' in tick and tick['discipline'] is not None:
                    tick['discipline'] = tick['discipline'].lower()
                    
                tick_obj = UserTicks(**tick)
                if tags_list:
                    # Store tags_list as a set to ensure uniqueness
                    tick_obj._tags_list = set(tags_list)
                tick_objects.append(tick_obj)
            
            # Set user_id and created_at
            now = datetime.now(timezone.utc)
            for tick in tick_objects:
                tick.user_id = user_id
                tick.created_at = now
            
            # Add to session
            self.session.add_all(tick_objects)
            await self.session.flush()
            
            logger.info("Successfully saved new user ticks", extra={
                "user_id": str(user_id),
                "saved_count": len(tick_objects),
                "skipped_count": skipped_count,
                "timestamp": now.isoformat()
            })
            
            return tick_objects
            
        except Exception as e:
            await self.session.rollback()
            logger.error("Error saving user ticks", extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError(f"Error saving user ticks: {str(e)}")
    
    async def save_performance_pyramid(
        self,
        pyramid_data: List[Dict[str, Any]],
        user_id: UUID
    ) -> List[PerformancePyramid]:
        """Save performance pyramid data to database"""
        logger.info("Saving performance pyramid", extra={
            "user_id": str(user_id),
            "entry_count": len(pyramid_data)
        })
        
        try:
            # Create PerformancePyramid objects
            pyramid_objects = [PerformancePyramid(**entry) for entry in pyramid_data]
            
            # Set user_id
            for pyramid in pyramid_objects:
                pyramid.user_id = user_id
            
            # Add to session
            self.session.add_all(pyramid_objects)
            await self.session.flush()
            
            logger.info("Successfully saved performance pyramid", extra={
                "user_id": str(user_id),
                "saved_count": len(pyramid_objects),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return pyramid_objects
            
        except Exception as e:
            await self.session.rollback()
            logger.error("Error saving performance pyramid", extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError(f"Error saving performance pyramid: {str(e)}")
    
    async def save_tags(self, tag_names: List[str], tick_ids: List[int]) -> List[Tag]:
        """Save tags and create associations with ticks."""
        logger.info("Saving tags and associations", extra={"tag_count": len(tag_names), "tick_count": len(tick_ids)})
        try:
            tag_objects = []
            new_tags = 0
            existing_tags = 0

            # Get or create tags first
            unique_tag_names = set(tag_names)  # Ensure uniqueness
            for name in unique_tag_names:
                stmt = select(Tag).where(Tag.name == name)
                result = await self.session.execute(stmt)
                tag = result.scalar_one_or_none()
                if not tag:
                    tag = Tag(name=name)
                    self.session.add(tag)
                    new_tags += 1
                else:
                    existing_tags += 1
                tag_objects.append(tag)

            await self.session.flush()  # Ensure tags have IDs

            # Eagerly load ticks with their existing tags
            stmt = select(UserTicks).where(
                and_(
                    UserTicks.id.in_(tick_ids),
                    ~UserTicks.id.in_(
                        select(UserTicksTags.user_tick_id).where(
                            UserTicksTags.tag_id.in_([tag.id for tag in tag_objects])
                        )
                    )
                )
            ).options(selectinload(UserTicks.tags))
            
            result = await self.session.execute(stmt)
            ticks = result.scalars().all()

            if not ticks:
                logger.warning("No ticks found for tag association")
                return tag_objects

            # Create associations only for ticks that don't already have these tags
            associations_created = 0
            for tick in ticks:
                if hasattr(tick, '_tags_list') and tick._tags_list:
                    existing_tag_names = {tag.name for tag in tick.tags}
                    for tag_name in tick._tags_list:
                        matching_tag = next((tag for tag in tag_objects if tag.name == tag_name), None)
                        if matching_tag and matching_tag.name not in existing_tag_names:
                            association = UserTicksTags(
                                user_tick_id=tick.id,
                                tag_id=matching_tag.id
                            )
                            self.session.add(association)
                            associations_created += 1

            await self.session.flush()

            logger.info("Successfully saved tags and associations", extra={
                "total_tags": len(tag_objects),
                "new_tags": new_tags,
                "existing_tags": existing_tags,
                "associations_created": associations_created
            })
            return tag_objects

        except Exception as e:
            await self.session.rollback()
            logger.error("Error saving tags", extra={"error": str(e), "traceback": traceback.format_exc()})
            raise DatabaseError(f"Error saving tags: {str(e)}")
        
    async def update_sync_timestamp(self, user_id: UUID, logbook_type: LogbookType, profile_url: str = None) -> None:
        """Update user's logbook sync timestamp and URL if provided"""
        logger.info("Updating sync timestamp", extra={"user_id": str(user_id), "logbook_type": logbook_type.value, "profile_url": profile_url})
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                logger.error("User not found", extra={"user_id": str(user_id)})
                raise DatabaseError(f"User {user_id} not found")
            
            now = datetime.now(timezone.utc)
            if logbook_type == LogbookType.MOUNTAIN_PROJECT:
                user.mountain_project_last_sync = now
                if profile_url:
                    user.mountain_project_url = str(profile_url) 
            elif logbook_type == LogbookType.EIGHT_A_NU:
                user.eight_a_nu_last_sync = now
                if profile_url:
                    user.eight_a_nu_url = profile_url 
            
            await self.session.flush()
            logger.info("Successfully updated sync timestamp", extra={
                "user_id": str(user_id),
                "logbook_type": logbook_type.value,
                "timestamp": now.isoformat(),
                "profile_url": profile_url
            })
        except Exception as e:
            logger.error("Error updating sync timestamp", extra={"user_id": str(user_id), "logbook_type": logbook_type.value, "error": str(e)})
            raise DatabaseError(f"Error updating sync timestamp: {str(e)}")

    async def update_eight_a_nu_credentials(self, user_id: UUID, username: str, password: str) -> None:
        """Update user's hashed 8a.nu credentials"""
        logger.info("Updating 8a.nu credentials", extra={"user_id": str(user_id)})
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error("User not found", extra={"user_id": str(user_id)})
                raise DatabaseError(f"User {user_id} not found")
            
            # Hash credentials using the same mechanism as user passwords
            hashed_username = get_password_hash(username)
            hashed_password = get_password_hash(password)
            
            # Update hashed credentials
            user.eight_a_nu_hashed_username = hashed_username
            user.eight_a_nu_hashed_password = hashed_password
            
            await self.session.flush()
            logger.info("Successfully updated 8a.nu credentials", extra={
                "user_id": str(user_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error("Error updating 8a.nu credentials", extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError(f"Error updating 8a.nu credentials: {str(e)}")

    async def get_user_ticks(
        self,
        user_id: UUID,
        include_tags: bool = False
    ) -> List[UserTicks]:
        """Get user's ticks from database"""
        logger.info("Retrieving user ticks", extra={
            "user_id": str(user_id),
            "include_tags": include_tags
        })
        
        try:
            # Build query
            stmt = select(UserTicks).where(UserTicks.user_id == user_id)
            if include_tags:
                stmt = stmt.options(selectinload(UserTicks.tags))
            
            # Execute query
            result = await self.session.execute(stmt)
            ticks = result.scalars().all()
            
            logger.info("Successfully retrieved user ticks", extra={
                "user_id": str(user_id),
                "tick_count": len(ticks),
                "tags_included": include_tags
            })
            
            return list(ticks)
            
        except Exception as e:
            logger.error("Error retrieving user ticks", extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError(f"Error retrieving user ticks: {str(e)}")
    
    async def get_performance_pyramid(
        self,
        user_id: UUID
    ) -> List[PerformancePyramid]:
        """Get user's performance pyramid from database"""
        logger.info("Retrieving performance pyramid", extra={
            "user_id": str(user_id)
        })
        
        try:
            # Build and execute query
            stmt = select(PerformancePyramid).where(
                PerformancePyramid.user_id == user_id
            )
            result = await self.session.execute(stmt)
            pyramids = result.scalars().all()
            
            logger.info("Successfully retrieved performance pyramid", extra={
                "user_id": str(user_id),
                "pyramid_count": len(pyramids)
            })
            
            return list(pyramids)
            
        except Exception as e:
            logger.error("Error retrieving performance pyramid", extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DatabaseError(f"Error retrieving performance pyramid: {str(e)}")
    
    async def cleanup(self) -> None:
        """Close the database session"""
        logger.debug("Cleaning up database session")
        try:
            await self.session.close()
            logger.debug("Database session closed successfully")
        except Exception as e:
            logger.error("Error closing database session", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
