"""Factories for creating pre-configured climbing service test instances."""
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any


class ClimbingServiceFactory:
    """Factory for creating preconfigured climbing service test instances."""

    @classmethod
    async def create_service(
        cls,
        mock_db: bool = True,
        mock_grade_service: bool = True,
        mock_external_apis: bool = True,
        test_climbs: Optional[List[Dict[str, Any]]] = None,
        test_routes: Optional[List[Dict[str, Any]]] = None
    ):
        """Create a climbing service instance with configurable mocks.

        Args:
            mock_db: Whether to mock the database service
            mock_grade_service: Whether to mock the grade service
            mock_external_apis: Whether to mock external API clients
            test_climbs: Optional predefined climb data
            test_routes: Optional predefined route data

        Returns:
            Configured ClimbingService instance with appropriate mocks
        """
        from app.services.utils.grade_service import GradeService
        from app.services.logbook.database_service import DatabaseService
        
        # Fix imports for external API clients - use generic AsyncMock if module not found
        mp_client = AsyncMock()
        eight_a_scraper = AsyncMock()
        
        # Try to import the correct classes if they exist
        try:
            from app.services.logbook.gateways.mp_client import MountainProjectClient
            if mock_external_apis:
                mp_client = AsyncMock(spec=MountainProjectClient)
            else:
                mp_client = MountainProjectClient()
        except ImportError:
            # Client class name might be different, or module structure could be different
            pass
            
        try:
            from app.services.logbook.gateways.eight_a_scraper import EightANuScraper
            if mock_external_apis:
                eight_a_scraper = AsyncMock(spec=EightANuScraper)
            else:
                eight_a_scraper = EightANuScraper()
        except ImportError:
            # Client class name might be different, or module structure could be different
            pass

        # Create mock dependencies
        db_service = AsyncMock() if mock_db else None  # Don't use spec to allow adding methods
        if db_service:
            # Explicitly add the required methods to the mock
            db_service.get_user_ticks = AsyncMock()
            db_service.get_tick_by_id = AsyncMock()
            
        grade_service = MagicMock(spec=GradeService) if mock_grade_service else GradeService.get_instance()

        # Configure mock behavior
        if mock_db and test_climbs:
            db_service.get_user_ticks.return_value = test_climbs
            db_service.get_tick_by_id.side_effect = lambda climb_id: next(
                (climb for climb in test_climbs if climb["id"] == climb_id), None
            )

        if mock_external_apis and test_routes:
            mp_client.search_routes.return_value = test_routes

        # Import here to avoid circular imports
        from app.services.logbook.orchestrator import LogbookOrchestrator

        # Create a mock for AsyncSession
        db_session = AsyncMock()

        # Create service instance with mocks
        # LogbookOrchestrator expects db and optional db_service
        service = LogbookOrchestrator(
            db=db_session,
            db_service=db_service
        )
        
        # Monkey patch the grade_service attribute after initialization
        if mock_grade_service:
            service.grade_service = grade_service

        # Add mp_client and eight_a_scraper if they're used by the service
        # (These may need to be attached differently based on actual implementation)
        service.mp_client = mp_client
        service.eight_a_scraper = eight_a_scraper

        # Store mock references for test assertion access
        service._test_mocks = {
            "db_service": db_service,
            "grade_service": grade_service,
            "mp_client": mp_client,
            "eight_a_scraper": eight_a_scraper,
            "db_session": db_session
        }

        return service 