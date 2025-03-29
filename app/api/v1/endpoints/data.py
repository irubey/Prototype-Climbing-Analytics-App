from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import math

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import User, UserTicks, PerformancePyramid, UserTicksTags, Tag
from app.models.enums import ClimbingDiscipline
from app.schemas.data import (
    TickCreate,
    BatchTickCreate,
    PyramidInput,
    RefreshStatus,
    TickResponse,
    UserTicksWithTags,
    LogbookBatchUpdate,
    LogbookBatchUpdateResponse,
    TagResponse
)
from app.services.utils.grade_service import GradeService, GradingSystem

router = APIRouter()

@router.get("/ticks", response_model=List[UserTicksWithTags])
async def get_user_ticks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all ticks for the authenticated user with tags and performance data."""
    result = await db.execute(
        select(UserTicks)
        .filter(UserTicks.user_id == current_user.id)
        .options(
            selectinload(UserTicks.tags),
            selectinload(UserTicks.performance_pyramid)
        )
    )
    ticks = result.scalars().all()

    # Format response
    response = []
    for tick in ticks:
        performance_data = (
            tick.performance_pyramid[0].__dict__ if tick.performance_pyramid else None
        )
        if performance_data:
            # Remove internal SQLAlchemy fields and unwanted keys
            performance_data.pop('_sa_instance_state', None)
            performance_data.pop('user_id', None)
            performance_data.pop('tick_id', None)
            performance_data.pop('id', None)

        # Convert quality scores from 0-1 to 0-5 scale
        route_quality = None if tick.route_quality is None or math.isnan(tick.route_quality) else tick.route_quality * 5
        user_quality = None if tick.user_quality is None or math.isnan(tick.user_quality) else tick.user_quality * 5

        response.append(
            UserTicksWithTags(
                id=tick.id,
                user_id=tick.user_id,
                route_name=tick.route_name,
                tick_date=tick.tick_date,
                route_grade=tick.route_grade,
                binned_grade=tick.binned_grade,
                binned_code=tick.binned_code,
                length=tick.length,
                pitches=tick.pitches,
                location=tick.location,
                location_raw=tick.location_raw,
                lead_style=tick.lead_style,
                discipline=tick.discipline,
                send_bool=tick.send_bool,
                route_url=tick.route_url,
                created_at=tick.created_at.date(),
                notes=tick.notes,
                route_quality=route_quality,
                user_quality=user_quality,
                logbook_type=tick.logbook_type,
                tags=[TagResponse(id=tag.id, name=tag.name) for tag in tick.tags],
                performance_pyramid=performance_data
            )
        )

    return response

@router.get("/pyramid", response_model=dict)
async def get_performance_pyramid(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch performance pyramid data for the authenticated user."""
    result = await db.execute(
        select(UserTicks)
        .join(PerformancePyramid, UserTicks.id == PerformancePyramid.tick_id)
        .filter(UserTicks.user_id == current_user.id)
        .options(
            selectinload(UserTicks.tags),
            selectinload(UserTicks.performance_pyramid)
        )
    )
    ticks = result.scalars().all()

    detailed_data = []
    for tick in ticks:
        # Safely get pyramid data if it exists
        pyramid_data = None
        if tick.performance_pyramid and len(tick.performance_pyramid) > 0:
            pyramid = tick.performance_pyramid[0]
            try:
                # Safely handle enum values
                crux_angle = pyramid.crux_angle.value if hasattr(pyramid.crux_angle, 'value') else pyramid.crux_angle
                crux_energy = pyramid.crux_energy.value if hasattr(pyramid.crux_energy, 'value') else pyramid.crux_energy
                
                pyramid_data = {
                    "first_sent": pyramid.first_sent,
                    "crux_angle": crux_angle,
                    "crux_energy": crux_energy,
                    "num_attempts": pyramid.num_attempts,
                    "days_attempts": pyramid.days_attempts,
                    "num_sends": pyramid.num_sends,
                    "description": pyramid.description,
                    "agg_notes": pyramid.agg_notes
                }
            except Exception as e:
                logger.error(f"Error processing pyramid data for tick {tick.id}", extra={
                    "error": str(e),
                    "tick_id": tick.id,
                    "pyramid_id": pyramid.id if pyramid else None
                })
                continue  # Skip this tick if we can't process its pyramid data

        # Safely handle quality scores
        try:
            route_quality = None if tick.route_quality is None or math.isnan(tick.route_quality) else tick.route_quality * 5
        except (ValueError, TypeError):
            route_quality = None

        try:
            user_quality = None if tick.user_quality is None or math.isnan(tick.user_quality) else tick.user_quality * 5
        except (ValueError, TypeError):
            user_quality = None

        detailed_data.append(
            UserTicksWithTags(
                id=tick.id,
                user_id=tick.user_id,
                route_name=tick.route_name,
                tick_date=tick.tick_date,
                route_grade=tick.route_grade,
                binned_grade=tick.binned_grade,
                binned_code=tick.binned_code,
                length=tick.length,
                pitches=tick.pitches,
                location=tick.location,
                location_raw=tick.location_raw,
                lead_style=tick.lead_style,
                discipline=tick.discipline,
                send_bool=tick.send_bool,
                route_url=tick.route_url,
                created_at=tick.created_at.date(),
                notes=tick.notes,
                route_quality=route_quality,
                user_quality=user_quality,
                logbook_type=tick.logbook_type,
                tags=[TagResponse(id=tag.id, name=tag.name) for tag in tick.tags],
                performance_pyramid=pyramid_data
            )
        )

    return {"detailed_data": detailed_data}

@router.post("/ticks/batch", response_model=LogbookBatchUpdateResponse)
async def batch_update_ticks(
    batch_update: LogbookBatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Batch create, update, and delete ticks with associated performance data."""
    grade_service = GradeService.get_instance()
    created_ids = []
    updated_ids = []
    deleted_ids = []
    errors = {"creates": {}, "updates": {}, "deletes": {}}

    # Process creates
    for idx, tick_data in enumerate(batch_update.creates):
        try:
            binned_code = await grade_service.convert_to_code(
                tick_data.route_grade, GradingSystem.YDS
            )
            db_tick = UserTicks(
                user_id=current_user.id,
                binned_code=binned_code,
                **tick_data.model_dump(exclude={"id", "performance_data", "tags"})
            )
            db.add(db_tick)
            await db.flush()

            # Handle tags
            if tick_data.tags:
                for tag_name in tick_data.tags:
                    tag = await db.execute(
                        select(Tag).filter(Tag.name == tag_name)
                    )
                    tag = tag.scalar_one_or_none()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        await db.flush()
                    db.add(UserTicksTags(user_tick_id=db_tick.id, tag_id=tag.id))

            # Handle performance data
            if tick_data.performance_data:
                pyramid = PerformancePyramid(
                    user_id=current_user.id,
                    tick_id=db_tick.id,
                    **tick_data.performance_data.model_dump()
                )
                db.add(pyramid)

            created_ids.append(db_tick.id)
        except Exception as e:
            errors["creates"][idx] = str(e)

    # Process updates
    for idx, tick_data in enumerate(batch_update.updates):
        try:
            if not tick_data.id:
                raise ValueError("Tick ID required for update")
            tick = await db.execute(
                select(UserTicks)
                .filter(UserTicks.id == tick_data.id, UserTicks.user_id == current_user.id)
            )
            tick = tick.scalar_one_or_none()
            if not tick:
                raise HTTPException(status_code=404, detail="Tick not found")

            binned_code = await grade_service.convert_to_code(
                tick_data.route_grade, GradingSystem.YDS
            )
            update_data = tick_data.model_dump(exclude={"id", "performance_data", "tags"})
            update_data["binned_code"] = binned_code
            await db.execute(
                update(UserTicks)
                .where(UserTicks.id == tick_data.id)
                .values(**update_data)
            )

            # Update tags
            if tick_data.tags is not None:
                await db.execute(
                    delete(UserTicksTags).filter(UserTicksTags.user_tick_id == tick_data.id)
                )
                for tag_name in tick_data.tags:
                    tag = await db.execute(
                        select(Tag).filter(Tag.name == tag_name)
                    )
                    tag = tag.scalar_one_or_none()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        await db.flush()
                    db.add(UserTicksTags(user_tick_id=tick_data.id, tag_id=tag.id))

            # Update or create performance data
            if tick_data.performance_data:
                pyramid = await db.execute(
                    select(PerformancePyramid)
                    .filter(PerformancePyramid.tick_id == tick_data.id)
                )
                pyramid = pyramid.scalar_one_or_none()
                if pyramid:
                    await db.execute(
                        update(PerformancePyramid)
                        .where(PerformancePyramid.tick_id == tick_data.id)
                        .values(**tick_data.performance_data.model_dump())
                    )
                else:
                    pyramid = PerformancePyramid(
                        user_id=current_user.id,
                        tick_id=tick_data.id,
                        **tick_data.performance_data.model_dump()
                    )
                    db.add(pyramid)

            updated_ids.append(tick_data.id)
        except Exception as e:
            errors["updates"][idx] = str(e)

    # Process deletes
    for idx, tick_id in enumerate(batch_update.deletes):
        try:
            tick = await db.execute(
                select(UserTicks)
                .filter(UserTicks.id == tick_id, UserTicks.user_id == current_user.id)
            )
            tick = tick.scalar_one_or_none()
            if not tick:
                raise HTTPException(status_code=404, detail="Tick not found")

            await db.execute(
                delete(PerformancePyramid).filter(PerformancePyramid.tick_id == tick_id)
            )
            await db.execute(
                delete(UserTicksTags).filter(UserTicksTags.user_tick_id == tick_id)
            )
            await db.execute(
                delete(UserTicks).filter(UserTicks.id == tick_id)
            )
            deleted_ids.append(tick_id)
        except Exception as e:
            errors["deletes"][idx] = str(e)

    await db.commit()

    # Clean up empty error dictionaries
    if not errors["creates"]:
        errors.pop("creates")
    if not errors["updates"]:
        errors.pop("updates")
    if not errors["deletes"]:
        errors.pop("deletes")
    errors = errors if errors else None

    return LogbookBatchUpdateResponse(
        success=True,
        created=created_ids,
        updated=updated_ids,
        deleted=deleted_ids,
        errors=errors
    )

@router.delete("/ticks/{tick_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tick(
    tick_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a specific tick and its associated performance pyramid data."""
    tick = await db.execute(
        select(UserTicks)
        .filter(UserTicks.id == tick_id, UserTicks.user_id == current_user.id)
    )
    tick = tick.scalar_one_or_none()
    
    if not tick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tick not found or not owned by user"
        )
    
    await db.execute(
        delete(PerformancePyramid).filter(PerformancePyramid.tick_id == tick_id)
    )
    await db.execute(
        delete(UserTicksTags).filter(UserTicksTags.user_tick_id == tick_id)
    )
    await db.execute(
        delete(UserTicks).filter(UserTicks.id == tick_id)
    )
    
    await db.commit()

@router.post("/pyramid", response_model=PyramidInput)
async def update_pyramid(
    pyramid_data: PyramidInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update or create performance pyramid data for an existing tick."""
    tick = await db.execute(
        select(UserTicks)
        .filter(UserTicks.id == pyramid_data.tick_id, UserTicks.user_id == current_user.id)
    )
    tick = tick.scalar_one_or_none()
    
    if not tick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tick not found or not owned by user"
        )
    
    pyramid = await db.execute(
        select(PerformancePyramid)
        .filter(PerformancePyramid.tick_id == pyramid_data.tick_id)
    )
    pyramid = pyramid.scalar_one_or_none()
    
    if pyramid:
        await db.execute(
            update(PerformancePyramid)
            .where(PerformancePyramid.tick_id == pyramid_data.tick_id)
            .values(**pyramid_data.model_dump(exclude={'tick_id'}))
        )
    else:
        pyramid = PerformancePyramid(
            user_id=current_user.id,
            **pyramid_data.model_dump()
        )
        db.add(pyramid)
    
    await db.commit()
    await db.refresh(pyramid)
    return pyramid_data