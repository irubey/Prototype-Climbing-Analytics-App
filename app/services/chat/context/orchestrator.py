from typing import Dict, List, Optional, Callable
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from redis.client import Redis
import asyncio

from app.services.chat.context.data_aggregator import DataAggregator
from app.services.chat.context.context_enhancer import ContextEnhancer
from app.services.chat.context.unified_formatter import UnifiedFormatter
from app.services.chat.context.cache_manager import CacheManager

class ContextOrchestrator:
    """
    Orchestrates the context system components to provide unified context for AI responses.
    Coordinates data aggregation, enhancement, formatting, and caching.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        cache_ttl: int = 3600,
        cache_prefix: str = "context:"
    ):
        """
        Initialize the context orchestrator with its components.
        
        Args:
            db_session: SQLAlchemy async session
            redis_client: Redis client instance
            cache_ttl: Cache TTL in seconds (default 1 hour)
            cache_prefix: Cache key prefix
        """
        self.data_aggregator = DataAggregator(db_session)
        self.context_enhancer = ContextEnhancer()
        self.formatter = UnifiedFormatter()
        self.cache_manager = CacheManager(
            redis_client=redis_client,
            ttl_seconds=cache_ttl,
            prefix=cache_prefix
        )

    async def get_context(
        self,
        user_id: int,
        query: Optional[str] = None,
        conversation_id: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        Main method to get context for AI responses.
        
        Args:
            user_id: User ID
            query: Optional user query for relevance scoring
            conversation_id: Optional conversation ID
            force_refresh: Whether to force context regeneration
            
        Returns:
            Formatted context data
        """
        if force_refresh:
            await self.cache_manager.invalidate_context(user_id, conversation_id)
            
        context = await self.cache_manager.get_or_set_context(
            user_id,
            conversation_id,
            lambda: self._generate_context(user_id, query)
        )
        
        if context and query and 'relevance' not in context:
            # Update relevance scores for new query
            context = await self._update_relevance(context, query, user_id, conversation_id)
            
        return context

    async def _generate_context(
        self,
        user_id: int,
        query: Optional[str] = None
    ) -> Dict:
        """
        Generates fresh context by coordinating all components.
        
        Args:
            user_id: User ID
            query: Optional user query
            
        Returns:
            Generated context data
        """
        # Step 1: Aggregate raw data
        raw_data = await self.data_aggregator.aggregate_all_data(user_id)
        
        # Step 2: Enhance with trends and insights
        enhanced_data = await self.context_enhancer.enhance_context(raw_data, query)
        
        # Step 3: Format into unified structure (synchronous call)
        formatted_context = self.formatter.format_context(enhanced_data, query)
        
        return formatted_context

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
        enhanced_data = await self.context_enhancer.enhance_context(context, query)
        # Format context (synchronous call)
        updated_context = self.formatter.format_context(enhanced_data, query)
        
        # Update cache
        await self.cache_manager.update_context(
            user_id,
            updated_context,
            conversation_id,
            merge=True
        )
        
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
            await self.cache_manager.invalidate_context(user_id, conversation_id)
            
            # Generate fresh context
            new_context = await self._generate_context(user_id)
            
            # Cache new context
            success = await self.cache_manager.set_context(
                user_id,
                new_context,
                conversation_id
            )
            
            return success
            
        except Exception as e:
            print(f"Error handling data update: {str(e)}")  # Replace with proper logging
            return False

    async def refresh_context(
        self,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Refreshes context data while maintaining cache TTL.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID
            
        Returns:
            Success status
        """
        try:
            # Generate fresh context
            new_context = await self._generate_context(user_id)
            
            # Update cache with fresh data
            success = await self.cache_manager.set_context(
                user_id,
                new_context,
                conversation_id
            )
            
            return success
            
        except Exception as e:
            print(f"Error refreshing context: {str(e)}")  # Replace with proper logging
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
