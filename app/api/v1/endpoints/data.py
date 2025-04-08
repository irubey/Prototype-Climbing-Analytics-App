from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import math
import pandas as pd

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import User, UserTicks, PerformancePyramid, UserTicksTags, Tag
from app.models.enums import ClimbingDiscipline
from app.schemas.data import (
    PyramidInput,
    PerformancePyramidResponse,
    UserTicksWithTags,
    LogbookBatchUpdate,
    LogbookBatchUpdateResponse,
    TagResponse
)
from app.services.utils.grade_service import GradeService, GradingSystem
from app.core.logging import logger
from app.services.logbook.climb_classifier import ClimbClassifier
from app.services.logbook.pyramid_builder import PyramidBuilder
from app.services.logbook.database_service import DatabaseService
from app.services.logbook.recalculation_service import RecalculationService

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
            PerformancePyramidResponse.from_orm(tick.performance_pyramid[0])
            if tick.performance_pyramid
            else None
            )

        # Convert quality scores from 0-1 to 0-5 scale
        route_quality = None if tick.route_quality is None or math.isnan(tick.route_quality) else tick.route_quality * 5
        user_quality = None if tick.user_quality is None or math.isnan(tick.user_quality) else tick.user_quality * 5

        # Build the full response object
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
                cur_max_sport=tick.cur_max_sport,
                cur_max_trad=tick.cur_max_trad,
                cur_max_boulder=tick.cur_max_boulder,
                cur_max_tr=tick.cur_max_tr,
                cur_max_alpine=tick.cur_max_alpine,
                cur_max_winter_ice=tick.cur_max_winter_ice,
                cur_max_aid=tick.cur_max_aid,
                cur_max_mixed=tick.cur_max_mixed,
                difficulty_category=tick.difficulty_category,
                discipline=tick.discipline,
                send_bool=tick.send_bool,
                length_category=tick.length_category,
                season_category=tick.season_category,
                route_url=tick.route_url,
                created_at=tick.created_at,  # Keeping as datetime; adjust to .date() if preferred
                notes=tick.notes,
                route_quality=route_quality,
                user_quality=user_quality,
                logbook_type=tick.logbook_type,
                tags=[TagResponse(id=tag.id, name=tag.name) for tag in tick.tags],
                performance_pyramid=performance_data
            )
        )

    # Log the response data, including data[9] specifically
    logger.info("Outgoing ticks data", extra={
        "total_ticks": len(response),
        "sample_tick": response[9].model_dump() if len(response) > 9 else None,
        "first_tick": response[0].model_dump() if response else None,
        "last_tick": response[-1].model_dump() if response else None
    })

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

    # Process creates (unchanged, requires full data)
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

            if tick_data.tags:
                for tag_name in tick_data.tags:
                    tag = await db.execute(select(Tag).filter(Tag.name == tag_name))
                    tag = tag.scalar_one_or_none()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        await db.flush()
                    db.add(UserTicksTags(user_tick_id=db_tick.id, tag_id=tag.id))

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

    # Process updates (handle partial data)
    for idx, tick_data in enumerate(batch_update.updates):
        try:
            tick = await db.execute(
                select(UserTicks)
                .filter(UserTicks.id == tick_data.id, UserTicks.user_id == current_user.id)
            )
            tick = tick.scalar_one_or_none()
            if not tick:
                raise HTTPException(status_code=404, detail="Tick not found")

            # Filter out None values and exclude performance_data and tags for base update
            update_data = {
                k: v for k, v in tick_data.model_dump(exclude={"id", "performance_data", "tags"}).items()
                if v is not None
            }
            if "route_grade" in update_data:
                update_data["binned_code"] = await grade_service.convert_to_code(
                    update_data["route_grade"], GradingSystem.YDS
                )

            if update_data:
                await db.execute(
                    update(UserTicks)
                    .where(UserTicks.id == tick_data.id)
                    .values(**update_data)
                )

            # Update tags if provided (even if empty)
            if tick_data.tags is not None:
                await db.execute(
                    delete(UserTicksTags).filter(UserTicksTags.user_tick_id == tick_data.id)
                )
                for tag_name in tick_data.tags:
                    tag = await db.execute(select(Tag).filter(Tag.name == tag_name))
                    tag = tag.scalar_one_or_none()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        await db.flush()
                    db.add(UserTicksTags(user_tick_id=tick_data.id, tag_id=tag.id))

            # Update performance data if provided
            if tick_data.performance_data is not None:
                pyramid = await db.execute(
                    select(PerformancePyramid)
                    .filter(PerformancePyramid.tick_id == tick_data.id)
                )
                pyramid = pyramid.scalar_one_or_none()
                performance_data = {
                    k: v for k, v in tick_data.performance_data.model_dump().items()
                    if v is not None
                }
                if pyramid:
                    if performance_data:
                        await db.execute(
                            update(PerformancePyramid)
                            .where(PerformancePyramid.tick_id == tick_data.id)
                            .values(**performance_data)
                        )
                else:
                    pyramid = PerformancePyramid(
                        user_id=current_user.id,
                        tick_id=tick_data.id,
                        **performance_data
                    )
                    db.add(pyramid)

            updated_ids.append(tick_data.id)
        except Exception as e:
            errors["updates"][idx] = str(e)

    # Process deletes (unchanged)
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

    recalculation_service = RecalculationService(db)
    success, recalculation_errors = await recalculation_service.recalculate_fields_and_pyramids(
        current_user.id, created_ids, updated_ids, deleted_ids
    )

    if not success:
        # Format recalculation errors to match the expected schema
        formatted_recalculation_errors = {
            "recalculation": {
                idx: str(error) for idx, error in enumerate(recalculation_errors)
            }
        }
        if errors is None:
            errors = formatted_recalculation_errors
        else:
            errors.update(formatted_recalculation_errors)

    # Clean up empty error dictionaries
    if errors and not errors.get("creates"):
        errors.pop("creates", None)
    if errors and not errors.get("updates"):
        errors.pop("updates", None)
    if errors and not errors.get("deletes"):
        errors.pop("deletes", None)
    if errors and not errors.get("recalculation"):
        errors.pop("recalculation", None)
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