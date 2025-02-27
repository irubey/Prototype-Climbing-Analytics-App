from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import User, UserTicks, PerformancePyramid
from app.schemas.data import (
    TickCreate,
    BatchTickCreate,
    PyramidInput,
    RefreshStatus
)

from app.services.utils.grade_service import GradeService, GradingSystem

router = APIRouter()

@router.post("/ticks/batch", response_model=List[int])
async def create_ticks_batch(
    ticks: BatchTickCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create multiple ticks in batch."""
    tick_ids = []
    grade_service = GradeService.get_instance()
    
    for tick_data in ticks.ticks:
        try:
            # Convert grade to binned code using GradeService
            binned_code = await grade_service.convert_to_code(
                tick_data.route_grade,
                GradingSystem.YDS  # Assuming YDS for routes, you may need to adjust based on your needs
            )
            
            # Create tick
            db_tick = UserTicks(
                user_id=current_user.id,
                binned_code=binned_code,
                **tick_data.model_dump(exclude={'performance_data'})
            )
            db.add(db_tick)
            await db.flush()
            
            # Create performance pyramid if performance data exists
            if tick_data.performance_data:
                pyramid = PerformancePyramid(
                    user_id=current_user.id,
                    tick_id=db_tick.id,
                    **tick_data.performance_data.model_dump()
                )
                db.add(pyramid)
            
            tick_ids.append(db_tick.id)
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid grade: {tick_data.route_grade}"
            )
    
    await db.commit()
    return tick_ids

@router.delete("/ticks/{tick_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tick(
    tick_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a specific tick and its associated performance pyramid data."""
    # Verify ownership and existence
    tick = await db.execute(
        select(UserTicks)
        .filter(UserTicks.id == tick_id, UserTicks.user_id == current_user.id)
    )
    tick = await tick.scalar_one_or_none()
    
    if not tick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tick not found or not owned by user"
        )
    
    # Delete associated pyramid data
    await db.execute(
        delete(PerformancePyramid)
        .filter(PerformancePyramid.tick_id == tick_id)
    )
    
    # Delete tick
    await db.execute(
        delete(UserTicks)
        .filter(UserTicks.id == tick_id)
    )
    
    await db.commit()

@router.post("/pyramid", response_model=PyramidInput)
async def update_pyramid(
    pyramid_data: PyramidInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update performance pyramid data with manual input."""
    # Verify tick ownership
    tick = await db.execute(
        select(UserTicks)
        .filter(UserTicks.id == pyramid_data.tick_id, UserTicks.user_id == current_user.id)
    )
    tick = await tick.scalar_one_or_none()
    
    if not tick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tick not found or not owned by user"
        )
    
    # Update or create pyramid data
    pyramid = await db.execute(
        select(PerformancePyramid)
        .filter(PerformancePyramid.tick_id == pyramid_data.tick_id)
    )
    pyramid = await pyramid.scalar_one_or_none()
    
    if pyramid:
        for field, value in pyramid_data.model_dump(exclude={'tick_id'}).items():
            if value is not None:
                setattr(pyramid, field, value)
    else:
        pyramid = PerformancePyramid(
            user_id=current_user.id,
            **pyramid_data.model_dump()
        )
        db.add(pyramid)
    
    await db.commit()
    await db.refresh(pyramid)
    return pyramid_data

@router.post("/refresh", response_model=RefreshStatus)
async def refresh_data(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Refresh user's logbook data."""
    if not current_user.mountain_project_url or not current_user.eight_a_nu_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logbook URL not configured"
        )
    
    #TODO: background_tasks.add_task(
    #TODO:     refresh_mountain_project_data,
    #TODO:     user_id=current_user.id,
    #TODO:     mp_url=current_user.mountain_project_url
    #TODO: )
    
    return RefreshStatus(
        status="pending",
        message="Data refresh initiated in background"
    ) 