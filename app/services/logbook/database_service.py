"""
Database service for logbook operations.

This module provides functionality for:
- Managing user ticks and performance data
- Handling tag operations
- Tracking sync status
- Bulk database operations
"""

from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import traceback

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
)
from app.db.session import get_db

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
        """Save user ticks to database"""
        logger.info("Saving user ticks", extra={
            "user_id": str(user_id),
            "tick_count": len(ticks_data)
        })
        
        try:
            # Create UserTicks objects
            tick_objects = [UserTicks(**tick) for tick in ticks_data]
            
            # Set user_id and created_at
            now = datetime.now(timezone.utc)
            for tick in tick_objects:
                tick.user_id = user_id
                tick.created_at = now
            
            # Add to session
            self.session.add_all(tick_objects)
            await self.session.flush()
            
            logger.info("Successfully saved user ticks", extra={
                "user_id": str(user_id),
                "saved_count": len(tick_objects),
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
        logger.info("Saving tags and associations", extra={"tag_count": len(tag_names), "tick_count": len(tick_ids)})
        try:
            tag_objects = []
            new_tags = 0
            existing_tags = 0

            # Eagerly load ticks with their tags
            stmt = select(UserTicks).where(UserTicks.id.in_(tick_ids)).options(selectinload(UserTicks.tags))
            result = await self.session.execute(stmt)
            ticks = result.scalars().all()

            if not ticks:
                logger.warning("No ticks found for tag association")
                return []

            # Get or create tags
            for name in tag_names:
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

            await self.session.flush()

            # Create associations
            associations_created = 0
            for tick in ticks:
                existing_tag_names = {tag.name for tag in tick.tags}  # Tags are already loaded
                for tag in tag_objects:
                    if tag.name not in existing_tag_names:
                        tick.tags.append(tag)
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
