from typing import Dict, List, Optional, Callable, Union, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from redis.client import Redis
import asyncio
from app.core.logging import logger
import json
from fastapi import HTTPException
from sqlalchemy import select

from app.services.chat.context.data_aggregator import DataAggregator
from app.services.chat.context.context_enhancer import ContextEnhancer
from app.services.chat.context.unified_formatter import UnifiedFormatter
from app.services.chat.context.cache_manager import CacheManager
from app.models import ClimberContext

class ContextOrchestrator:
    """
    Orchestrates the context system components to provide unified context for AI responses.
    Coordinates data aggregation, enhancement, formatting, and caching.
    """

    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client
        self.cache_ttl = 3600  # 1 hour
        self.cache_prefix = "context:"
        self.enhancer = ContextEnhancer()
        self.formatter = UnifiedFormatter()

    async def get_context(
        self,
        user_id: str,
        query: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get context for a user, either from cache or freshly generated."""
        try:
            logger.debug("Getting context", extra={
                "user_id": user_id,
                "force_refresh": force_refresh,
                "has_query": query is not None
            })

            # Try to get from cache first unless force refresh
            if not force_refresh:
                cached = await self._get_cached_context(user_id)
                if cached:
                    logger.debug("Found cached context", extra={"user_id": user_id})
                    if query:
                        cached = await self.enhancer.enhance_context(cached, query)
                    return cached

            logger.debug("Generating fresh context", extra={"user_id": user_id})
            data_aggregator = await DataAggregator.create()
            
            # Use the existing transaction from middleware
            raw_data = await data_aggregator.aggregate_all_data(self.db, user_id)
            
            # Enhance and format the context
            enhanced_data = await self.enhancer.enhance_context(raw_data, query)
            context = self.formatter.format_context(enhanced_data, query)
            
            # Cache the result
            await self._cache_context(user_id, context)
            
            logger.debug("Context generation completed", extra={"user_id": user_id})
            return context
            
        except Exception as e:
            logger.error("Context generation error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": user_id
            })
            raise HTTPException(
                status_code=500,
                detail=f"Error generating context: {str(e)}"
            )

    async def refresh_context(self, user_id: str) -> None:
        """Force refresh context for a user."""
        try:
            logger.debug("Starting context refresh", extra={"user_id": user_id})
            data_aggregator = await DataAggregator.create()
            
            # Use existing transaction from middleware
            raw_data = await data_aggregator.aggregate_all_data(self.db, user_id)
            
            # Enhance and format the context
            enhanced_data = await self.enhancer.enhance_context(raw_data)
            context = self.formatter.format_context(enhanced_data)
            
            # Cache the result
            await self._cache_context(user_id, context)
            logger.debug("Context refresh completed", extra={"user_id": user_id})
            
        except Exception as e:
            logger.error("Context refresh error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": user_id
            })
            raise HTTPException(
                status_code=500,
                detail=f"Error refreshing context: {str(e)}"
            )

    async def handle_data_update(
        self,
        user_id: str,
        update_type: str,
        update_data: Dict[str, Any],
        replace: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Handle updates to context data."""
        try:
            logger.debug("Handling data update", extra={
                "user_id": user_id,
                "update_type": update_type,
                "replace": replace
            })
            
            # Get current context using existing transaction
            data_aggregator = await DataAggregator.create()
            current_data = await data_aggregator.aggregate_all_data(self.db, user_id)
            
            if not current_data:
                logger.warning("No current data found for update", extra={"user_id": user_id})
                return None
                
            # Update the relevant section
            if replace:
                current_data[update_type] = update_data
            else:
                current_data[update_type].update(update_data)
                
            # Re-enhance and format the context
            enhanced_data = await self.enhancer.enhance_context(current_data)
            context = self.formatter.format_context(enhanced_data)
            
            # Cache the updated context
            await self._cache_context(user_id, context)
            
            logger.debug("Data update completed", extra={"user_id": user_id})
            return context
            
        except Exception as e:
            logger.error("Context update error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": user_id
            })
            raise HTTPException(
                status_code=500,
                detail=f"Error updating context: {str(e)}"
            )

    async def _get_cached_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get context from cache if it exists."""
        try:
            key = f"{self.cache_prefix}{user_id}"
            cached = await self.redis_client.get(key)
            return json.loads(cached) if cached else None
        except Exception as e:
            logger.error("Cache retrieval error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": user_id
            })
            return None

    async def _cache_context(self, user_id: str, context: Dict[str, Any]) -> None:
        """Cache context data."""
        try:
            key = f"{self.cache_prefix}{user_id}"
            await self.redis_client.setex(
                key,
                self.cache_ttl,
                json.dumps(context)
            )
        except Exception as e:
            logger.error("Cache storage error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": user_id
            })

    async def _generate_context(
        self,
        user_id: Union[int, str, UUID],
        query: Optional[str] = None
    ) -> Dict:
        """
        Generates fresh context by coordinating all components.
        
        Args:
            user_id: User ID
            query: Optional user query
            
        Returns:
            Generated context data with all required fields
        """
        try:
            # Create DataAggregator instance with current session
            data_aggregator = await DataAggregator.create()
            
            # Step 1: Aggregate raw data
            raw_data = await data_aggregator.aggregate_all_data(self.db, user_id)
            
            # Step 2: Enhance with trends and insights
            enhanced_data = await self.enhancer.enhance_context(raw_data, query)
            
            # Step 3: Format into unified structure
            formatted_context = self.formatter.format_context(enhanced_data, query)
            
            # Step 4: Ensure all required fields are present
            default_context = {
                "context_version": "1.0",
                "summary": "New user with no climbing history.",
                "profile": {},
                "performance": {},
                "trends": {},
                "relevance": {},
                "goals": {},
                "uploads": [],
                "is_new_user": True
            }
            
            # If we have actual data, update the default context
            if raw_data and raw_data.get('climber_context'):
                formatted_context = {**default_context, **formatted_context}
                formatted_context['is_new_user'] = False
                
                # NEW: Save context to ClimberContext model
                await self._save_context_to_db(user_id, formatted_context)
            else:
                formatted_context = default_context
            
            return formatted_context
            
        except Exception as e:
            logger.error(
                "Context generation error",
                extra={
                    "error": str(e),
                    "user_id": str(user_id)
                }
            )
            # Return default context structure even in error case
            return {
                "context_version": "1.0",
                "summary": "Unable to retrieve user context at this time.",
                "profile": {},
                "performance": {},
                "trends": {},
                "relevance": {},
                "goals": {},
                "uploads": [],
                "is_new_user": True
            }

    async def _save_context_to_db(
        self,
        user_id: Union[int, str, UUID],
        context: Dict[str, Any]
    ) -> None:
        """
        Saves the generated context to the ClimberContext model.
        
        Args:
            user_id: User ID
            context: Formatted context data
        """
        try:
            # Get or create ClimberContext record
            stmt = select(ClimberContext).where(ClimberContext.user_id == user_id)
            result = await self.db.execute(stmt)
            climber_context = result.scalar_one_or_none()
            
            if not climber_context:
                climber_context = ClimberContext(user_id=user_id)
                self.db.add(climber_context)
            
            # Update fields from context
            profile = context.get('profile', {})
            performance = context.get('performance', {})
            trends = context.get('trends', {})
            goals = context.get('goals', {})
            
            # Core Context
            climber_context.years_climbing = profile.get('years_climbing')
            climber_context.total_climbs = profile.get('total_climbs')
            climber_context.favorite_discipline = profile.get('favorite_discipline')
            climber_context.interests = profile.get('interests')
            climber_context.preferred_crag_last_year = profile.get('preferred_crag_last_year')
            
            # Performance Metrics
            highest_grades = performance.get('highest_grades', {})
            climber_context.highest_sport_grade_tried = highest_grades.get('sport')
            climber_context.highest_trad_grade_tried = highest_grades.get('trad')
            climber_context.highest_boulder_grade_tried = highest_grades.get('boulder')
            climber_context.highest_grade_sport_sent_clean_on_lead = highest_grades.get('sport')
            climber_context.highest_grade_trad_sent_clean_on_lead = highest_grades.get('trad')
            climber_context.highest_grade_boulder_sent_clean = highest_grades.get('boulder')
            
            # Onsight and Flash Grades
            climber_context.onsight_grade_sport = performance.get('onsight_grade_sport')
            climber_context.onsight_grade_trad = performance.get('onsight_grade_trad')
            climber_context.flash_grade_boulder = performance.get('flash_grade_boulder')
            
            # Grade Pyramids
            climber_context.grade_pyramid_sport = performance.get('grade_pyramid_sport', [])
            climber_context.grade_pyramid_trad = performance.get('grade_pyramid_trad', [])
            climber_context.grade_pyramid_boulder = performance.get('grade_pyramid_boulder', [])
            
            # Training Context
            climber_context.current_training_frequency = profile.get('training_frequency')
            climber_context.home_equipment = profile.get('home_equipment')
            
            # Goals
            climber_context.climbing_goals = goals.get('current_goals')
            
            # Recent Activity
            activity_levels = trends.get('activity_levels', {})
            climber_context.activity_last_30_days = activity_levels.get('monthly', 0)
            
            # Commit changes
            await self.db.commit()
            
            logger.info(
                "Saved context to database",
                extra={
                    "user_id": str(user_id),
                    "updated_fields": list(context.keys())
                }
            )
            
        except Exception as e:
            logger.error(
                "Error saving context to database",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "user_id": str(user_id)
                }
            )
            # Don't raise the error - we want to continue even if DB save fails
            await self.db.rollback()

    async def _update_relevance(
        self,
        context: Dict,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> Dict:
        """
        Updates context with new relevance scores for a query.
        
        Args:
            context: Existing context data
            query: User query
            user_id: User ID
            conversation_id: Optional conversation ID
            
        Returns:
            Updated context data
        """
        # Add relevance scores (async call)
        enhanced_data = await self.enhancer.enhance_context(context, query)
        # Format context (synchronous call)
        updated_context = self.formatter.format_context(enhanced_data, query)
        
        # Update cache
        await self._cache_context(str(user_id), updated_context)
        
        return updated_context

    async def handle_data_update(
        self,
        user_id: int,
        update_type: str,
        update_data: Dict,
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Handles updates to user data and refreshes context accordingly.
        
        Args:
            user_id: User ID
            update_type: Type of update (e.g., 'climber_context', 'ticks', 'performance')
            update_data: Updated data
            conversation_id: Optional conversation ID
            
        Returns:
            Success status
        """
        try:
            # Invalidate existing cache
            await self._cache_context(str(user_id), None)
            
            # Generate fresh context
            new_context = await self._generate_context(user_id)
            
            # Cache new context
            success = await self._cache_context(str(user_id), new_context)
            
            return success
            
        except Exception as e:
            print(f"Error handling data update: {str(e)}")  # Replace with proper logging
            return False

    async def refresh_context(
        self,
        user_id: Union[int, str, UUID],
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Refreshes context data while maintaining cache TTL.
        
        Args:
            user_id: User ID as UUID, string, or integer
            conversation_id: Optional conversation ID
            
        Returns:
            Success status
        """
        try:
            # Invalidate existing cache first
            await self._cache_context(str(user_id), None)
            
            # Generate fresh context
            new_context = await self._generate_context(user_id)
            
            # Update cache with fresh data
            success = await self._cache_context(str(user_id), new_context)
            
            if success:
                logger.info(
                    "Context refreshed successfully",
                    extra={
                        "user_id": str(user_id),
                        "conversation_id": conversation_id
                    }
                )
            else:
                logger.warning(
                    "Failed to set refreshed context in cache",
                    extra={
                        "user_id": str(user_id),
                        "conversation_id": conversation_id
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Error refreshing context",
                extra={
                    "error": str(e),
                    "user_id": str(user_id),
                    "conversation_id": conversation_id
                }
            )
            return False

    async def bulk_refresh_contexts(
        self,
        user_ids: List[int],
        batch_size: int = 50
    ) -> Dict[int, bool]:
        """
        Refreshes context data for multiple users in batches.
        
        Args:
            user_ids: List of user IDs to refresh
            batch_size: Number of contexts to refresh in parallel
            
        Returns:
            Dictionary mapping user IDs to success status
        """
        results = {}
        
        # Process in batches
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            
            # Refresh contexts in parallel
            refresh_tasks = [
                self.refresh_context(user_id)
                for user_id in batch
            ]
            
            # Gather results
            batch_results = await asyncio.gather(
                *refresh_tasks,
                return_exceptions=True
            )
            
            # Map results to user IDs
            for user_id, result in zip(batch, batch_results):
                results[user_id] = (
                    isinstance(result, bool) and result
                )
                
        return results

    async def cleanup_expired_contexts(self) -> int:
        """
        Removes expired context data from cache.
        
        Returns:
            Number of contexts cleaned up
        """
        try:
            # This is a placeholder - actual implementation would depend on
            # Redis configuration and cleanup strategy
            return 0
            
        except Exception as e:
            print(f"Error cleaning up contexts: {str(e)}")  # Replace with proper logging
            return 0
