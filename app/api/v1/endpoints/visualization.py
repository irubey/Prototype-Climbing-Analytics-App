from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.core.auth import (
    get_current_active_user,
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import (
    User,
    UserTicks,
    PerformancePyramid,
)
from app.models.enums import ClimbingDiscipline
from app.schemas.visualization import (
    DashboardBaseMetrics,
    DashboardPerformanceMetrics,
    PerformancePyramidData,
    BaseVolumeData,
    ProgressionData,
    LocationAnalysis,
    PerformanceCharacteristics
)
from app.services.dashboard.dashboard_analytics import get_dashboard_base_metrics, get_dashboard_performance_metrics

router = APIRouter()

# Helper functions for unit testing - these encapsulate database operations for easier mocking

async def get_performance_pyramid_data(db: AsyncSession, user_id: str, discipline: ClimbingDiscipline) -> Dict:
    """Get user's performance pyramid data for a specific discipline."""
    # Query first for user ticks with the given discipline and send status
    result = await db.execute(
        select(UserTicks)
        .filter(
            UserTicks.user_id == user_id,
            UserTicks.discipline == discipline,
            UserTicks.send_bool == True
        )
        .order_by(UserTicks.route_grade)
    )
    ticks = result.scalars().all()
    
    # Process pyramid data using the relationship
    grade_counts = {}
    pyramid_data = []
    
    for tick in ticks:
        # Only process ticks that have performance pyramid data
        if tick.performance_pyramid:
            grade = tick.route_grade
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
            # Add all performance pyramid entries to our list
            pyramid_data.extend(tick.performance_pyramid)
    
    return {
        "discipline": discipline,
        "grade_counts": grade_counts,
        "total_sends": len(pyramid_data)
    }

async def get_base_volume_data(db: AsyncSession, user_id: str) -> Dict:
    """Get user's base volume analysis data."""
    result = await db.execute(
        select(
            UserTicks.difficulty_category,
            func.count(UserTicks.id).label("count"),
            func.avg(UserTicks.length).label("avg_length")
        )
        .filter(UserTicks.user_id == user_id)
        .group_by(UserTicks.difficulty_category)
    )
    volume_data = result.all()

    return {
        "volume_by_difficulty": {
            category: {
                "count": count,
                "avg_length": float(avg_length) if avg_length else 0
            }
            for category, count, avg_length in volume_data
        }
    }

async def get_progression_data(db: AsyncSession, user_id: str) -> Dict:
    """Get user's progression analysis data."""
    result = await db.execute(
        select(UserTicks)
        .filter(
            UserTicks.user_id == user_id,
            UserTicks.send_bool == True
        )
        .order_by(UserTicks.tick_date)
    )
    ticks = result.scalars().all()

    # Process progression data
    progression_by_discipline = {}
    for tick in ticks:
        if tick.discipline not in progression_by_discipline:
            progression_by_discipline[tick.discipline] = []
        progression_by_discipline[tick.discipline].append({
            "date": tick.tick_date,
            "grade": tick.route_grade,
            "name": tick.route_name
        })

    return {
        "progression_by_discipline": progression_by_discipline
    }

async def get_location_analysis_data(db: AsyncSession, user_id: str) -> Dict:
    """Get user's climbing location analysis data."""
    # Get location distribution
    result = await db.execute(
        select(
            UserTicks.location,
            func.count(UserTicks.id).label("count"),
            func.array_agg(UserTicks.route_grade).label("grades")
        )
        .filter(UserTicks.user_id == user_id)
        .group_by(UserTicks.location)
    )
    location_data = result.all()

    # Get seasonal patterns
    result = await db.execute(
        select(
            UserTicks.season_category,
            func.count(UserTicks.id).label("count")
        )
        .filter(UserTicks.user_id == user_id)
        .group_by(UserTicks.season_category)
    )
    seasonal_data = {
        season: count
        for season, count in result.all()
    }

    return {
        "location_distribution": {
            location: {
                "count": count,
                "grades": grades
            }
            for location, count, grades in location_data
        },
        "seasonal_patterns": seasonal_data
    }

async def get_performance_characteristics_data(db: AsyncSession, user_id: str) -> Dict:
    """Get user's performance characteristics analysis data."""
    # First get all user ticks with performance pyramid data
    result = await db.execute(
        select(UserTicks)
        .filter(
            UserTicks.user_id == user_id,
            UserTicks.send_bool == True
        )
    )
    ticks = result.scalars().all()
    
    # Extract all performance pyramid entries
    performance_data = []
    for tick in ticks:
        if tick.performance_pyramid:
            performance_data.extend(tick.performance_pyramid)
    
    # Analyze performance characteristics
    angle_distribution = {}
    energy_distribution = {}
    crux_types = {}
    attempts_analysis = {
        "flash_rate": 0,
        "avg_attempts": 0,
        "max_attempts": 0
    }

    total_climbs = len(performance_data)
    if total_climbs > 0:
        for entry in performance_data:
            # Crux type analysis
            if hasattr(entry, 'crux_type') and entry.crux_type:
                crux_types[entry.crux_type] = crux_types.get(entry.crux_type, 0) + 1
            
            # Angle analysis
            if entry.crux_angle:
                angle_distribution[entry.crux_angle] = (
                    angle_distribution.get(entry.crux_angle, 0) + 1
                )

            # Energy type analysis
            if entry.crux_energy:
                energy_distribution[entry.crux_energy] = (
                    energy_distribution.get(entry.crux_energy, 0) + 1
                )

            # Attempts analysis
            if entry.num_attempts == 1:
                attempts_analysis["flash_rate"] += 1
            if entry.num_attempts:
                attempts_analysis["avg_attempts"] += entry.num_attempts
                attempts_analysis["max_attempts"] = max(
                    attempts_analysis["max_attempts"],
                    entry.num_attempts
                )

        attempts_analysis["flash_rate"] = attempts_analysis["flash_rate"] / total_climbs
        attempts_analysis["avg_attempts"] = attempts_analysis["avg_attempts"] / total_climbs

    return {
        "crux_types": crux_types,
        "angle_distribution": angle_distribution,
        "energy_distribution": energy_distribution,
        "attempts_analysis": attempts_analysis
    }

@router.get("/dashboard-base-metrics", response_model=DashboardBaseMetrics)
async def get_dashboard_data(
    time_range: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's climbing dashboard overview."""
    try:
        # Convert days to timedelta if specified
        filter_range = timedelta(days=time_range) if time_range else None
        
        # Get dashboard metrics using analytics service
        return await get_dashboard_base_metrics(
            db=db,
            user_id=current_user.id,
            time_range=filter_range
        )

    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch dashboard data"
        )

@router.get("/dashboard-performance-metrics", response_model=DashboardPerformanceMetrics)
async def get_performance_data(
    discipline: Optional[ClimbingDiscipline] = None,
    time_range: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's performance metrics."""
    try:
        # Convert days to timedelta if specified
        filter_range = timedelta(days=time_range) if time_range else None
        
        # Get performance metrics using analytics service
        return await get_dashboard_performance_metrics(
            db=db,
            user_id=current_user.id,
            discipline=discipline,
            time_range=filter_range
        )

    except Exception as e:
        logger.error(f"Error fetching performance data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch performance data"
        )

@router.get("/performance-pyramid", response_model=PerformancePyramidData)
async def get_performance_pyramid(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    discipline: ClimbingDiscipline = ClimbingDiscipline.SPORT
) -> Any:
    """Get user's performance pyramid for a specific discipline."""
    try:
        return await get_performance_pyramid_data(
            db=db,
            user_id=current_user.id,
            discipline=discipline
        )
    except Exception as e:
        logger.error(f"Error fetching performance pyramid: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch performance pyramid"
        )

@router.get("/base-volume", response_model=BaseVolumeData)
async def get_base_volume(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's base volume analysis."""
    try:
        return await get_base_volume_data(
            db=db,
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Error fetching base volume data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch base volume data"
        )

@router.get("/progression", response_model=ProgressionData)
async def get_progression(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's progression analysis."""
    try:
        return await get_progression_data(
            db=db,
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Error fetching progression data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch progression data"
        )

@router.get("/location-analysis", response_model=LocationAnalysis)
async def get_location_analysis(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's climbing location analysis."""
    try:
        return await get_location_analysis_data(
            db=db,
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Error fetching location analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch location analysis"
        )

@router.get("/performance-characteristics", response_model=PerformanceCharacteristics)
async def get_performance_characteristics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's performance characteristics analysis."""
    try:
        return await get_performance_characteristics_data(
            db=db,
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Error fetching performance characteristics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch performance characteristics"
        ) 