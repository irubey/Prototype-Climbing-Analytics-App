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
        result = await db.execute(
            select(PerformancePyramid)
            .join(UserTicks)
            .filter(
                PerformancePyramid.user_id == current_user.id,
                UserTicks.discipline == discipline,
                UserTicks.send_bool == True
            )
            .order_by(PerformancePyramid.binned_code.desc())
        )
        pyramid_data = result.scalars().all()

        # Process pyramid data
        grade_counts = {}
        for entry in pyramid_data:
            grade = entry.tick.route_grade
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        return {
            "discipline": discipline,
            "grade_counts": grade_counts,
            "total_sends": len(pyramid_data)
        }

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
        result = await db.execute(
            select(
                UserTicks.difficulty_category,
                func.count(UserTicks.id).label("count"),
                func.avg(UserTicks.length).label("avg_length")
            )
            .filter(UserTicks.user_id == current_user.id)
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
        result = await db.execute(
            select(UserTicks)
            .filter(
                UserTicks.user_id == current_user.id,
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
        # Get location distribution
        result = await db.execute(
            select(
                UserTicks.location,
                func.count(UserTicks.id).label("count"),
                func.array_agg(UserTicks.route_grade).label("grades")
            )
            .filter(UserTicks.user_id == current_user.id)
            .group_by(UserTicks.location)
        )
        location_data = result.all()

        # Get seasonal patterns
        result = await db.execute(
            select(
                UserTicks.season_category,
                func.count(UserTicks.id).label("count")
            )
            .filter(UserTicks.user_id == current_user.id)
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
        result = await db.execute(
            select(PerformancePyramid)
            .filter(PerformancePyramid.user_id == current_user.id)
        )
        performance_data = result.scalars().all()

        # Analyze performance characteristics
        angle_distribution = {}
        energy_distribution = {}
        attempts_analysis = {
            "flash_rate": 0,
            "avg_attempts": 0,
            "max_attempts": 0
        }

        total_climbs = len(performance_data)
        if total_climbs > 0:
            for entry in performance_data:
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
            "angle_distribution": angle_distribution,
            "energy_distribution": energy_distribution,
            "attempts_analysis": attempts_analysis
        }

    except Exception as e:
        logger.error(f"Error fetching performance characteristics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch performance characteristics"
        ) 