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
import math

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
        # Build base query without the invalid joinedload for location
        base_query = (
            select(UserTicks)
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
        
        # Safely process discipline stats with None checks
        discipline_stats = {}
        for discipline, count in result.all():
            # Handle None disciplines safely
            if discipline is None:
                discipline_key = "unknown"
            else:
                # Safe access to enum value with fallback to string representation
                discipline_key = discipline.value if hasattr(discipline, 'value') else str(discipline)
            discipline_stats[discipline_key] = count

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
        
        # Safely handle grade distribution
        grade_distribution = {}
        try:
            # Get all grades and counts, then sort manually with synchronous operations
            grade_count_pairs = [(grade or "unknown", count) for grade, count in result.all()]
            
            # Sort by grade complexity if possible, otherwise leave unsorted
            try:
                # Get numeric codes for grades
                grades_to_convert = [pair[0] for pair in grade_count_pairs if pair[0] != "unknown"]
                if grades_to_convert:
                    # Await the async conversion
                    grade_codes = await grade_service.convert_grades_to_codes(grades_to_convert)
                    
                    # Create a dictionary mapping grade to code for easy lookup
                    grade_to_code = {grade: code for grade, code in zip(grades_to_convert, grade_codes)}
                    
                    # Sort based on grade codes
                    sorted_pairs = sorted(
                        grade_count_pairs,
                        key=lambda x: grade_to_code.get(x[0], 0)
                    )
                    
                    # Convert to dictionary
                    grade_distribution = {grade: count for grade, count in sorted_pairs}
                else:
                    # If no valid grades, just create the dictionary unsorted
                    grade_distribution = {grade: count for grade, count in grade_count_pairs}
            except Exception as sort_err:
                logger.warning(f"Error sorting grades: {sort_err}")
                # Fallback to unsorted distribution
                grade_distribution = {grade: count for grade, count in grade_count_pairs}
        except Exception as grade_err:
            logger.warning(f"Error processing grade distribution: {grade_err}")
            # Fallback to unsorted distribution
            grade_distribution = {
                grade if grade else "unknown": count
                for grade, count in result.all()
            }

        total_climbs = sum(discipline_stats.values())

        # Use an explicit try/except when creating the model
        try:
            # Convert UserTicks to TickData objects properly
            tick_data_list = []
            for tick in recent_ticks:
                if tick:
                    try:
                        # Handle NaN values and check limits on binned_code
                        binned_code = tick.binned_code
                        route_quality = tick.route_quality
                        
                        # Ensure binned_code is within valid range
                        if binned_code is not None and (binned_code < 0 or binned_code > 200):
                            binned_code = None
                            
                        # Handle NaN in route_quality
                        if route_quality is not None and (isinstance(route_quality, float) and (math.isnan(route_quality) or route_quality > 5)):
                            route_quality = None
                        
                        # Create TickData from dictionary of attributes
                        tick_dict = {
                            "route_name": tick.route_name,
                            "route_grade": tick.route_grade,
                            "binned_grade": tick.binned_grade,
                            "binned_code": binned_code,
                            "tick_date": tick.tick_date,
                            "location": tick.location or "Unknown",
                            "discipline": tick.discipline,
                            "send_bool": tick.send_bool if tick.send_bool is not None else False,
                            "route_url": tick.route_url,
                            "route_quality": route_quality,
                            "logbook_type": tick.logbook_type,
                            "lead_style": tick.lead_style
                        }
                        tick_data = TickData.model_validate(tick_dict)
                        tick_data_list.append(tick_data)
                    except Exception as tick_err:
                        logger.warning(f"Error converting tick to TickData: {tick_err}")
                        continue

            metrics = DashboardBaseMetrics(
                recent_ticks=tick_data_list,
                discipline_stats=discipline_stats,
                grade_distribution=grade_distribution,
                total_climbs=total_climbs
            )
            return metrics
        except Exception as model_err:
            logger.error(f"Error creating dashboard metrics model: {model_err}")
            # Return an empty model if validation fails
            return DashboardBaseMetrics(
                recent_ticks=[],
                discipline_stats=discipline_stats,
                grade_distribution=grade_distribution,
                total_climbs=total_climbs
            )

    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}")
        # Return empty metrics instead of raising
        return DashboardBaseMetrics(
            recent_ticks=[],
            discipline_stats={},
            grade_distribution={},
            total_climbs=0
        )

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
        # Build base query with performance data - properly joining relationship properties
        base_query = (
            select(UserTicks)
            .options(
                joinedload(UserTicks.performance_pyramid),
                joinedload(UserTicks.tags)
            )
            .filter(UserTicks.user_id == user_id)
        )

        if discipline:
            base_query = base_query.filter(UserTicks.discipline == discipline)
            
        if time_range:
            cutoff_date = datetime.now() - time_range
            base_query = base_query.filter(UserTicks.tick_date >= cutoff_date)

        # Execute query and ensure proper unique() handling for collections
        result = await db.execute(base_query)
        ticks = result.unique().scalars().all()

        # Process metrics
        highest_grades = {}
        hard_sends = []
        
        for tick in ticks:
            # Skip ticks with no discipline
            if not tick or not tick.discipline:
                continue
                
            try:
                # Safely get discipline value
                discipline_str = tick.discipline.value if hasattr(tick.discipline, 'value') else str(tick.discipline)
                
                # Track highest grades
                current_grade = highest_grades.get(discipline_str)
                
                # Check if we have a current grade to compare against
                if not current_grade:
                    highest_grades[discipline_str] = tick.route_grade
                else:
                    # Check current max grades stored in the tick
                    if tick.discipline == ClimbingDiscipline.SPORT and tick.cur_max_rp_sport:
                        if tick.route_grade == tick.cur_max_rp_sport:
                            highest_grades[discipline_str] = tick.route_grade
                    elif tick.discipline == ClimbingDiscipline.TRAD and tick.cur_max_rp_trad:
                        if tick.route_grade == tick.cur_max_rp_trad:
                            highest_grades[discipline_str] = tick.route_grade
                    elif tick.discipline == ClimbingDiscipline.BOULDER and tick.cur_max_boulder:
                        if tick.route_grade == tick.cur_max_boulder:
                            highest_grades[discipline_str] = tick.route_grade
                    
                # Track hard sends based on difficulty_category (already calculated relative to user's max)
                if tick.difficulty_category and tick.difficulty_category.lower() in ['hard', 'very hard', 'max']:
                    hard_sends.append(tick)
                    
            except Exception as tick_err:
                logger.warning(f"Error processing tick: {tick_err}")
                continue

        # Create metrics with safe sorting
        try:
            # Sort hard sends safely
            sorted_hard_sends = []
            if hard_sends:
                try:
                    sorted_hard_sends = sorted(
                        hard_sends,
                        key=lambda x: x.tick_date if hasattr(x, 'tick_date') else datetime.min,
                        reverse=True
                    )[:10]  # Top 10 hard sends
                except Exception as sort_err:
                    logger.warning(f"Error sorting hard sends: {sort_err}")
                    sorted_hard_sends = hard_sends[:10]  # Use unsorted if sorting fails
            
            return DashboardPerformanceMetrics(
                highest_grades=highest_grades,
                latest_hard_sends=sorted_hard_sends
            )
        except Exception as metrics_err:
            logger.error(f"Error creating performance metrics: {metrics_err}")
            # Return empty metrics if creation fails
            return DashboardPerformanceMetrics(
                highest_grades={},
                latest_hard_sends=[]
            )

    except Exception as e:
        logger.error(f"Error fetching performance metrics: {e}")
        # Return empty metrics instead of raising
        return DashboardPerformanceMetrics(
            highest_grades={},
            latest_hard_sends=[]
        )

async def get_overview_analytics(
    db: AsyncSession,
    user_id: UUID,
    time_range: Optional[timedelta] = None
) -> Dict:
    """Get comprehensive climbing overview analytics.
    
    This function combines functionality from dashboard base metrics and performance metrics
    to provide a complete overview of a user's climbing history, stats and performance.
    
    Args:
        db: Async database session
        user_id: User ID to get metrics for
        time_range: Optional time range to filter metrics
        
    Returns:
        Dictionary containing aggregated climbing data including:
        - Recent climbing history
        - Lifetime statistics
        - Top performances across all disciplines
        
    Raises:
        ValueError: If user_id is invalid
        SQLAlchemyError: If database query fails
    """
    try:
        # Get base metrics (recent history, discipline stats, grade distribution)
        base_metrics = await get_dashboard_base_metrics(
            db=db,
            user_id=user_id,
            time_range=time_range
        )
        
        # Get performance metrics for all disciplines
        performance_metrics = {}
        
        # Safely iterate through disciplines, handling None values
        for discipline in list(ClimbingDiscipline):
            try:
                # Skip if discipline is None
                if discipline is None:
                    continue
                    
                discipline_metrics = await get_dashboard_performance_metrics(
                    db=db,
                    user_id=user_id,
                    discipline=discipline,
                    time_range=None  # Use full lifetime for top performances
                )
                
                # Safely get discipline value with fallback
                discipline_key = discipline.value if discipline and hasattr(discipline, 'value') else str(discipline)
                performance_metrics[discipline_key] = discipline_metrics
            except Exception as e:
                logger.warning(f"Error processing discipline {discipline}: {e}")
                # Continue with other disciplines even if one fails
                continue
        
        # Get max grades across all disciplines directly from the database
        max_grades_query = (
            select(
                UserTicks.discipline,
                func.max(UserTicks.cur_max_rp_sport).label("max_sport"),
                func.max(UserTicks.cur_max_rp_trad).label("max_trad"),
                func.max(UserTicks.cur_max_boulder).label("max_boulder")
            )
            .filter(UserTicks.user_id == user_id)
            .group_by(UserTicks.discipline)
        )
        max_grades_result = await db.execute(max_grades_query)
        max_grades_by_discipline = {
            (getattr(row[0], 'value') if hasattr(row[0], 'value') else str(row[0])): {
                'sport': row[1],
                'trad': row[2],
                'boulder': row[3]
            }
            for row in max_grades_result.all()
        }
        
        # Also get distribution of difficulty categories
        difficulty_dist_query = (
            select(
                UserTicks.difficulty_category,
                func.count(UserTicks.id).label("count")
            )
            .filter(UserTicks.user_id == user_id)
            .group_by(UserTicks.difficulty_category)
        )
        difficulty_result = await db.execute(difficulty_dist_query)
        difficulty_distribution = {
            category if category else "unknown": count
            for category, count in difficulty_result.all()
        }
        
        # Calculate all-time stats (regardless of time_range)
        all_time_query = (
            select(func.count(UserTicks.id))
            .filter(UserTicks.user_id == user_id)
        )
        result = await db.execute(all_time_query)
        lifetime_total = result.scalar_one()
        
        # Get first climb date (for lifetime duration)
        first_climb_query = (
            select(func.min(UserTicks.tick_date))
            .filter(UserTicks.user_id == user_id)
        )
        result = await db.execute(first_climb_query)
        first_climb_date = result.scalar_one()
        
        # Calculate climbing longevity in days - ensure date types match
        climbing_days = 0
        if first_climb_date:
            try:
                # Convert date to datetime if needed
                if isinstance(first_climb_date, datetime):
                    first_climb_datetime = first_climb_date
                else:
                    # If it's a date object, convert to datetime
                    first_climb_datetime = datetime.combine(first_climb_date, datetime.min.time())
                    
                # Calculate difference using datetime objects
                climbing_days = (datetime.now() - first_climb_datetime).days
            except Exception as date_err:
                logger.warning(f"Error calculating climbing days: {date_err}")
        
        # Compile comprehensive overview with safe access to nested data
        overview_data = {
            "recent_activity": {
                "recent_ticks": base_metrics.recent_ticks if hasattr(base_metrics, 'recent_ticks') else [],
                "time_range": time_range.days if time_range else None
            },
            "lifetime_stats": {
                "total_climbs": lifetime_total or 0,
                "climbing_days": climbing_days,
                "first_climb_date": first_climb_date,
                "discipline_distribution": base_metrics.discipline_stats if hasattr(base_metrics, 'discipline_stats') else {},
                "grade_distribution": base_metrics.grade_distribution if hasattr(base_metrics, 'grade_distribution') else {},
                "difficulty_distribution": difficulty_distribution
            },
            "max_grades": max_grades_by_discipline,
            "top_performances": {}
        }
        
        # Safely build top performances with explicit None checks
        for discipline, metrics in performance_metrics.items():
            if metrics is None:
                continue
                
            highest_grade = metrics.highest_grades.get(discipline) if hasattr(metrics, 'highest_grades') and metrics.highest_grades else None
            hard_sends = []
            
            if hasattr(metrics, "latest_hard_sends") and metrics.latest_hard_sends:
                for tick in metrics.latest_hard_sends[:3]:  # Top 3 hard sends
                    if tick is None:
                        continue
                    
                    # Ensure date is serializable
                    tick_date = tick.tick_date
                    if hasattr(tick_date, 'isoformat'):
                        tick_date = tick_date.isoformat()
                        
                    hard_sends.append({
                        "route_name": tick.route_name,
                        "grade": tick.route_grade,
                        "date": tick_date,
                        "location": tick.location if hasattr(tick, 'location') else None,
                        "difficulty_category": tick.difficulty_category
                    })
            
            overview_data["top_performances"][discipline] = {
                "highest_grade": highest_grade,
                "hard_sends": hard_sends
            }
        
        return overview_data
    
    except Exception as e:
        logger.error(f"Error fetching overview analytics: {e}")
        # Return empty data rather than failing completely
        return {
            "recent_activity": {"recent_ticks": [], "time_range": None},
            "lifetime_stats": {"total_climbs": 0, "climbing_days": 0, "first_climb_date": None, 
                              "discipline_distribution": {}, "grade_distribution": {}, "difficulty_distribution": {}},
            "max_grades": {},
            "top_performances": {}
        }


