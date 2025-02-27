"""
Dashboard analytics and visualization service.

This module provides services for:
- Generating climbing metrics
- Performance analysis
- Progress tracking
- Location-based analytics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import logger
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType
)
from app.models import (
    UserTicks,
)
from app.schemas.visualization import (
    DashboardBaseMetrics,
    DashboardPerformanceMetrics,
    TickData,
)
from app.services.utils.grade_service import GradeService

async def get_dashboard_base_metrics(
    db: AsyncSession,
    user_id: UUID,
    time_range: Optional[timedelta] = None
) -> DashboardBaseMetrics:
    """Get user's climbing dashboard metrics.
    
    Retrieves and processes basic climbing metrics including:
    - Recent climbing activity
    - Distribution across disciplines
    - Grade distribution
    - Total climb count
    
    Args:
        db: Async database session
        user_id: User ID to get metrics for
        time_range: Optional time range to filter metrics
        
    Returns:
        DashboardBaseMetrics containing aggregated climbing data
        
    Raises:
        ValueError: If user_id is invalid
        SQLAlchemyError: If database query fails
    """
    try:
        # Build base query with efficient joins
        base_query = (
            select(UserTicks)
            .options(joinedload(UserTicks.location))
            .filter(UserTicks.user_id == user_id)
        )
        
        # Apply time range filter if specified
        if time_range:
            cutoff_date = datetime.now() - time_range
            base_query = base_query.filter(UserTicks.tick_date >= cutoff_date)

        # Get recent ticks with full route data
        recent_ticks_query = (
            base_query
            .order_by(desc(UserTicks.tick_date))
            .limit(50)
        )
        result = await db.execute(recent_ticks_query)
        recent_ticks = result.scalars().all()

        # Get discipline distribution with efficient counting
        discipline_query = (
            select(
                UserTicks.discipline,
                func.count(UserTicks.id).label("count")
            )
            .filter(UserTicks.user_id == user_id)
            .group_by(UserTicks.discipline)
        )
        result = await db.execute(discipline_query)
        discipline_stats = {
            discipline.value: count
            for discipline, count in result.all()
        }

        # Get grade distribution with proper ordering
        grade_service = GradeService.get_instance()
        grade_query = (
            select(
                UserTicks.route_grade,
                func.count(UserTicks.id).label("count")
            )
            .filter(UserTicks.user_id == user_id)
            .group_by(UserTicks.route_grade)
        )
        result = await db.execute(grade_query)
        grade_distribution = {
            grade: count
            for grade, count in sorted(
                result.all(),
                key=lambda x: grade_service.convert_grades_to_codes([x[0]])[0]
            )
        }

        total_climbs = sum(discipline_stats.values())

        return DashboardBaseMetrics(
            recent_ticks=[TickData.model_validate(tick) for tick in recent_ticks],
            discipline_stats=discipline_stats,
            grade_distribution=grade_distribution,
            total_climbs=total_climbs
        )

    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}")
        raise

async def get_dashboard_performance_metrics(
    db: AsyncSession,
    user_id: UUID,
    discipline: Optional[ClimbingDiscipline] = None,
    time_range: Optional[timedelta] = None
) -> DashboardPerformanceMetrics:
    """Get user's performance metrics and analysis.
    
    Retrieves and processes advanced performance metrics including:
    - Highest achieved grades by discipline
    - Recent significant sends
    - Performance characteristics
    - Progress tracking
    
    Args:
        db: Async database session
        user_id: User ID to get metrics for
        discipline: Optional discipline to filter metrics
        time_range: Optional time range to filter metrics
        
    Returns:
        DashboardPerformanceMetrics containing performance analysis
        
    Raises:
        ValueError: If user_id is invalid
        SQLAlchemyError: If database query fails
    """
    try:
        # Build base query with performance data
        base_query = (
            select(UserTicks)
            .options(
                joinedload(UserTicks.performance_pyramid),
                joinedload(UserTicks.location)
            )
            .filter(UserTicks.user_id == user_id)
        )

        if discipline:
            base_query = base_query.filter(UserTicks.discipline == discipline)
            
        if time_range:
            cutoff_date = datetime.now() - time_range
            base_query = base_query.filter(UserTicks.tick_date >= cutoff_date)

        # Execute query once and process results
        result = await db.execute(base_query)
        ticks = result.scalars().all()

        # Process metrics
        grade_service = GradeService.get_instance()
        highest_grades = {}
        hard_sends = []
        
        for tick in ticks:
            # Track highest grades
            discipline_str = tick.discipline.value
            current_grade = highest_grades.get(discipline_str)
            if not current_grade or grade_service.is_harder_grade(
                tick.route_grade,
                current_grade,
                tick.discipline
            ):
                highest_grades[discipline_str] = tick.route_grade
                
            # Track hard sends
            if grade_service.is_hard_send(tick.route_grade, tick.discipline):
                hard_sends.append(tick)

        return DashboardPerformanceMetrics(
            highest_grades=highest_grades,
            latest_hard_sends=sorted(
                hard_sends,
                key=lambda x: x.tick_date,
                reverse=True
            )[:10]
        )

    except Exception as e:
        logger.error(f"Error fetching performance metrics: {e}")
        raise