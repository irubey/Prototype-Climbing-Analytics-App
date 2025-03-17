from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from datetime import timedelta
from uuid import UUID

from app.core.auth import (
    get_current_active_user,
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import (
    User,
    UserTicks,
)
from app.models.enums import ClimbingDiscipline
from app.schemas.visualization import (
    PerformancePyramidData,
    BaseVolumeData,
    OverviewAnalytics,

)
from app.services.dashboard.dashboard_analytics import get_overview_analytics

router = APIRouter()

# Helper functions for unit testing - these encapsulate database operations for easier mocking

async def get_performance_pyramid_data(db: AsyncSession, user_id: UUID, discipline: ClimbingDiscipline) -> Dict:
    """Get user's performance pyramid data with detailed climbing and performance information."""
    # Query for user ticks with the given discipline and send status, with joined performance pyramid data
    result = await db.execute(
        select(UserTicks)
        .filter(
            UserTicks.user_id == user_id,
            UserTicks.discipline == discipline,
            UserTicks.send_bool.is_(True)
        )
        .options(
            joinedload(UserTicks.performance_pyramid),
            joinedload(UserTicks.tags)
        )
        .order_by(UserTicks.route_grade)
    )
    ticks = result.unique().scalars().all()
    
    # Process pyramid data using the relationship
    detailed_pyramid_data = []
    grade_counts = {}
    
    for tick in ticks:
        if tick.performance_pyramid:
            # Add to grade counts for summary stats
            grade = tick.route_grade
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
            
            # Build detailed data with both tick and performance pyramid information
            for pyramid_entry in tick.performance_pyramid:
                entry_data = {
                    # UserTicks fields
                    "route_name": tick.route_name,
                    "tick_date": tick.tick_date,
                    "route_grade": tick.route_grade,
                    "binned_grade": tick.binned_grade,
                    "binned_code": tick.binned_code,
                    "length": tick.length,
                    "pitches": tick.pitches,
                    "location": tick.location,
                    "location_raw": tick.location_raw,
                    "lead_style": tick.lead_style,
                    "cur_max_sport": tick.cur_max_sport,
                    "cur_max_trad": tick.cur_max_trad,
                    "cur_max_boulder": tick.cur_max_boulder,
                    "difficulty_category": tick.difficulty_category,
                    "discipline": tick.discipline.value if tick.discipline else None,
                    "send_bool": tick.send_bool,
                    "length_category": tick.length_category,
                    "season_category": tick.season_category,
                    "route_url": tick.route_url,
                    "notes": tick.notes,
                    "route_quality": tick.route_quality,
                    "user_quality": tick.user_quality,
                    "logbook_type": tick.logbook_type.value if tick.logbook_type else None,
                    "tags": [tag.name for tag in tick.tags] if tick.tags else [],
                    
                    # PerformancePyramid fields
                    "first_sent": pyramid_entry.first_sent,
                    "crux_angle": pyramid_entry.crux_angle.value if pyramid_entry.crux_angle else None,
                    "crux_energy": pyramid_entry.crux_energy.value if pyramid_entry.crux_energy else None,
                    "num_attempts": pyramid_entry.num_attempts,
                    "days_attempts": pyramid_entry.days_attempts,
                    "num_sends": pyramid_entry.num_sends,
                    "description": pyramid_entry.description,
                    "agg_notes": pyramid_entry.agg_notes
                }
                detailed_pyramid_data.append(entry_data)
    
    return {
        "discipline": discipline.value,
        "grade_counts": grade_counts,
        "total_sends": len(detailed_pyramid_data),
        "detailed_data": detailed_pyramid_data
    }

async def get_base_volume_data(db: AsyncSession, user_id: UUID) -> Dict:
    """Get user's base volume analysis data with detailed climbing information."""
    result = await db.execute(
        select(UserTicks)
        .filter(UserTicks.user_id == user_id)
        .options(joinedload(UserTicks.tags))
    )
    ticks_data = result.unique().scalars().all()

    volume_data = []
    for tick in ticks_data:
        tick_data = {
            "route_name": tick.route_name,
            "tick_date": tick.tick_date,
            "route_grade": tick.route_grade,
            "binned_grade": tick.binned_grade,
            "binned_code": tick.binned_code,
            "length": tick.length,
            "pitches": tick.pitches,
            "location": tick.location,
            "location_raw": tick.location_raw,
            "lead_style": tick.lead_style,
            "cur_max_sport": tick.cur_max_sport,
            "cur_max_trad": tick.cur_max_trad,
            "cur_max_boulder": tick.cur_max_boulder,
            "cur_max_tr": tick.cur_max_tr,
            "cur_max_alpine": tick.cur_max_alpine,
            "cur_max_winter_ice": tick.cur_max_winter_ice,
            "cur_max_aid": tick.cur_max_aid,
            "cur_max_mixed": tick.cur_max_mixed,
            "difficulty_category": tick.difficulty_category,
            "discipline": tick.discipline.value if tick.discipline else None,
            "send_bool": tick.send_bool,
            "length_category": tick.length_category,
            "season_category": tick.season_category,
            "route_url": tick.route_url,
            "notes": tick.notes,
            "route_quality": tick.route_quality,
            "user_quality": tick.user_quality,
            "logbook_type": tick.logbook_type.value if tick.logbook_type else None,
            "tags": [tag.name for tag in tick.tags] if tick.tags else []
        }
        volume_data.append(tick_data)

    return {
        "ticks_data": volume_data
    }



@router.get("/overview-analytics", response_model=OverviewAnalytics)
async def get_overview_data(
    time_range: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's climbing overview analytics."""
    try:
        # Convert days to timedelta if specified
        filter_range = timedelta(days=time_range) if time_range else None
        
        # Get overview analytics using analytics service
        return await get_overview_analytics(
            db=db,
            user_id=current_user.id,
            time_range=filter_range
        )

    except Exception as e:
        logger.error(f"Error fetching overview analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch overview analytics"
        )

@router.get("/performance-pyramid", response_model=PerformancePyramidData)
async def get_performance_pyramid(
    discipline: ClimbingDiscipline = ClimbingDiscipline.SPORT,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
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