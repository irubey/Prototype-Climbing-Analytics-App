from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import logger
from app.models import UserTicks
from app.models.enums import ClimbingDiscipline

async def get_overview_analytics(
    db: AsyncSession,
    user_id: UUID,
    time_range: Optional[timedelta] = None
) -> Dict:
    """Get comprehensive climbing overview analytics based on specified requirements.

    Args:
        db: Async database session
        user_id: User ID to get metrics for
        time_range: Optional time range to filter certain metrics (defaults to None for lifetime data)

    Returns:
        Dictionary containing:
        - base_metrics: Favorite locations, discipline distribution, total pitches, etc.
        - performance_metrics: Recent hard sends, best performances, send rate, etc.
    """
    try:
        # Calculate cutoff date if time_range is provided (None means lifetime data)
        cutoff_date = datetime.now() - time_range if time_range else None

        # Base filter for queries that may be time-filtered
        base_filter = [UserTicks.user_id == user_id]
        if cutoff_date:
            base_filter.append(UserTicks.tick_date >= cutoff_date)

        # Helper function to convert UserTicks to a dict with required fields
        def tick_to_dict(tick, include_notes=False):
            base_dict = {
                "route_name": tick.route_name,
                "tick_date": tick.tick_date.isoformat() if tick.tick_date else None,
                "route_grade": tick.route_grade,
                "binned_code": tick.binned_code,
                "location": tick.location,
                "lead_style": tick.lead_style,
                "difficulty_category": tick.difficulty_category,
                "discipline": tick.discipline.value if tick.discipline else None,
                "tags": [tag.name for tag in tick.tags] if tick.tags else [],
            }
            if include_notes:
                base_dict["notes"] = tick.notes
            
            # Add performance pyramid data (assuming one entry per tick)
            if tick.performance_pyramid:
                pyramid = tick.performance_pyramid[0]  # Take the first entry
                base_dict["num_attempts"] = pyramid.num_attempts
                base_dict["days_attempts"] = pyramid.days_attempts
            else:
                base_dict["num_attempts"] = None
                base_dict["days_attempts"] = None
            
            return base_dict

        ### Base Metrics ###

        # 1. Favorite Locations - Top 3 locations with the highest sum of pitches
        favorite_locations_query = (
            select(UserTicks.location, func.sum(UserTicks.pitches).label("pitch_sum"))
            .filter(*base_filter)
            .group_by(UserTicks.location)
            .order_by(desc("pitch_sum"))
            .limit(3)
        )
        favorite_locations_result = await db.execute(favorite_locations_query)
        favorite_locations = [
            {"location": row[0], "pitch_sum": row[1]}
            for row in favorite_locations_result.all()
            if row[0]
        ]

        # 2. Discipline Distribution
        discipline_query = (
            select(UserTicks.discipline, func.count(UserTicks.id).label("count"))
            .filter(*base_filter)
            .group_by(UserTicks.discipline)
        )
        discipline_result = await db.execute(discipline_query)
        discipline_stats = {
            discipline.value if discipline else "unknown": count
            for discipline, count in discipline_result.all()
        }

        # 3. Total Pitches - Sum of user_ticks.pitches
        total_pitches_query = select(func.sum(UserTicks.pitches)).filter(*base_filter)
        total_pitches_result = await db.execute(total_pitches_query)
        total_pitches = total_pitches_result.scalar_one() or 0

        # 4. Unique Locations - Count of unique locations and unique states
        unique_locations_query = select(UserTicks.location).distinct().filter(*base_filter)
        unique_locations_result = await db.execute(unique_locations_query)
        unique_locations_list = [row[0] for row in unique_locations_result.all() if row[0]]

        unique_states = set()
        for loc in unique_locations_list:
            if loc:
                parts = loc.split(',')
                if len(parts) >= 2:
                    state = parts[-1].strip()
                    unique_states.add(state)

        unique_locations = {
            "num_unique_locations": len(unique_locations_list),
            "num_unique_states": len(unique_states)
        }

        # 5. Total Days Outside - Count of unique tick_date values
        total_days_outside_query = select(func.count(func.distinct(UserTicks.tick_date))).filter(*base_filter)
        total_days_outside_result = await db.execute(total_days_outside_query)
        total_days_outside = total_days_outside_result.scalar_one() or 0

        # 6. First Day Recorded Outside - Earliest tick_date (not filtered by time_range)
        first_day_query = select(func.min(UserTicks.tick_date)).filter(UserTicks.user_id == user_id)
        first_day_result = await db.execute(first_day_query)
        first_day = first_day_result.scalar_one()

        ### Performance Metrics ###

        # 1. Recent Hard Sends - Filtered by time_range and difficulty_category
        recent_hard_sends_filter = [
            UserTicks.user_id == user_id,
            UserTicks.difficulty_category.in_(["Project", "Tier2", "Tier3"])
        ]
        if cutoff_date:
            recent_hard_sends_filter.append(UserTicks.tick_date >= cutoff_date)

        recent_hard_sends_query = (
            select(UserTicks)
            .filter(*recent_hard_sends_filter)
            .options(
                joinedload(UserTicks.performance_pyramid),
                joinedload(UserTicks.tags)
            )
            .order_by(desc(UserTicks.tick_date))
        )
        recent_hard_sends_result = await db.execute(recent_hard_sends_query)
        recent_hard_sends_ticks = recent_hard_sends_result.unique().scalars().all()
        recent_hard_sends = [tick_to_dict(tick) for tick in recent_hard_sends_ticks]

        # 2. Best Performances - Max binned_code per discipline where send_bool is True (not filtered by time_range)
        best_performances = {}
        for discipline in ClimbingDiscipline:
            max_binned_code_query = (
                select(func.max(UserTicks.binned_code))
                .filter(
                    UserTicks.user_id == user_id,
                    UserTicks.discipline == discipline,
                    UserTicks.send_bool.is_(True)
                )
            )
            max_binned_code_result = await db.execute(max_binned_code_query)
            max_binned_code = max_binned_code_result.scalar_one()
            if max_binned_code is not None:
                best_sends_query = (
                    select(UserTicks)
                    .filter(
                        UserTicks.user_id == user_id,
                        UserTicks.discipline == discipline,
                        UserTicks.binned_code == max_binned_code,
                        UserTicks.send_bool.is_(True)
                    )
                    .options(
                        joinedload(UserTicks.performance_pyramid),
                        joinedload(UserTicks.tags)
                    )
                )
                best_sends_result = await db.execute(best_sends_query)
                best_sends_ticks = best_sends_result.unique().scalars().all()
                best_sends = [tick_to_dict(tick, include_notes=True) for tick in best_sends_ticks]
                best_performances[discipline.value] = best_sends

        # 3. Send Rate - Percentage of records where send_bool is True
        total_climbs_query = select(func.count(UserTicks.id)).filter(*base_filter)
        total_climbs_result = await db.execute(total_climbs_query)
        total_climbs = total_climbs_result.scalar_one() or 0

        total_sends_query = select(func.count(UserTicks.id)).filter(
            *base_filter,
            UserTicks.send_bool.is_(True)
        )
        total_sends_result = await db.execute(total_sends_query)
        total_sends = total_sends_result.scalar_one() or 0

        send_rate = (total_sends / total_climbs * 100) if total_climbs > 0 else 0

        # 4. Performance Attempts - Sum of pitches where difficulty_category is "Project"
        performance_attempts_query = (
            select(func.sum(UserTicks.pitches))
            .filter(
                *base_filter,
                UserTicks.difficulty_category == "Project"
            )
        )
        performance_attempts_result = await db.execute(performance_attempts_query)
        performance_attempts = performance_attempts_result.scalar_one() or 0

        # Structure the data as per the updated requirements
        overview_data = {
            "base_metrics": {
                "favorite_locations": favorite_locations,
                "discipline_distribution": discipline_stats,
                "total_pitches": total_pitches,
                "unique_locations": unique_locations,
                "total_days_outside": total_days_outside,
                "first_day_recorded": first_day.isoformat() if first_day else None
            },
            "performance_metrics": {
                "recent_hard_sends": recent_hard_sends,
                "best_performances": best_performances,
                "send_rate": round(send_rate, 2),
                "performance_attempts": performance_attempts
            }
        }

        return overview_data

    except Exception as e:
        logger.error(f"Error fetching overview analytics: {e}")
        # Return an empty data structure in case of failure
        return {
            "base_metrics": {
                "favorite_locations": [],
                "discipline_distribution": {},
                "total_pitches": 0,
                "unique_locations": {"num_unique_locations": 0, "num_unique_states": 0},
                "total_days_outside": 0,
                "first_day_recorded": None
            },
            "performance_metrics": {
                "recent_hard_sends": [],
                "best_performances": {},
                "send_rate": 0,
                "performance_attempts": 0
            }
        }