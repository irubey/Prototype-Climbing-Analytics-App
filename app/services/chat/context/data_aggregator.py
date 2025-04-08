from typing import Dict, List, Optional, Union
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from sqlalchemy import text, select
from sqlalchemy.orm import selectinload
from uuid import UUID
from app.core.exceptions import DatabaseError
from io import StringIO
from app.models import UserTicks
from app.models.enums import ClimbingDiscipline
from collections import Counter
from app.core.logging import logger

class DataAggregator:
    """
    Aggregates climber data from various sources including ClimberContext, UserTicks,
    PerformancePyramid, ChatHistory, and user uploads.
    """
    def __init__(self):
        self.supported_upload_formats = {'csv', 'json', 'txt'}

    @classmethod
    async def create(cls) -> 'DataAggregator':
        """Factory method to create DataAggregator instance."""
        return cls()

    async def fetch_climber_context(self, db_session: AsyncSession, user_id: Union[int, UUID, str]) -> Dict:
        try:
            logger.debug("Fetching climber context", extra={"user_id": str(user_id)})
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    raise DatabaseError(f"Invalid user_id format: badly formed hexadecimal UUID string")
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            query = text("""
                SELECT * FROM climber_context 
                WHERE user_id = :user_id
            """)
            result = await db_session.execute(query, {'user_id': user_id})
            row = result.first()
            logger.debug(f"Climber context fetch result: {'found' if row else 'not found'}", extra={"user_id": str(user_id)})
            return dict(row._mapping) if row else {}
        except Exception as e:
            logger.error("Error fetching climber context", extra={"error": str(e), "user_id": str(user_id)})
            raise DatabaseError(f"Error fetching climber context: {str(e)}")

    async def fetch_recent_ticks(self, db_session: AsyncSession, user_id: Union[int, UUID, str], days: int = 30) -> List[Dict]:
        try:
            logger.debug("Fetching recent ticks", extra={"user_id": str(user_id), "days": days})
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            cutoff_date = datetime.now() - timedelta(days=days)
            query = text("""
                SELECT 
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                FROM user_ticks 
                WHERE user_id = :user_id 
                AND tick_date >= :cutoff_date 
                ORDER BY tick_date DESC
            """)
            result = await db_session.execute(query, {'user_id': user_id, 'cutoff_date': cutoff_date})
            rows = result.fetchall()
            logger.debug(f"Fetched {len(rows)} recent ticks", extra={"user_id": str(user_id)})
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error("Error fetching recent ticks", extra={"error": str(e), "user_id": str(user_id)})
            raise DatabaseError(f"Error fetching recent ticks: {str(e)}")

    async def fetch_performance_metrics(self, db_session: AsyncSession, user_id: Union[int, UUID, str]) -> Dict:
        try:
            logger.debug("Fetching performance metrics", extra={"user_id": str(user_id)})
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            query = text("""
                SELECT * FROM performance_pyramid 
                WHERE user_id = :user_id
            """)
            result = await db_session.execute(query, {'user_id': user_id})
            row = result.first()
            logger.debug(f"Performance metrics fetch result: {'found' if row else 'not found'}", extra={"user_id": str(user_id)})
            return dict(row._mapping) if row else {}
        except Exception as e:
            logger.error("Error fetching performance metrics", extra={"error": str(e), "user_id": str(user_id)})
            raise DatabaseError(f"Error fetching performance metrics: {str(e)}")

    async def fetch_chat_history(
        self, 
        db_session: AsyncSession,
        user_id: Union[int, UUID, str], 
        conversation_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        try:
            logger.debug("Fetching chat history", extra={
                "user_id": str(user_id),
                "conversation_id": conversation_id,
                "limit": limit
            })
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)
            
            base_query = """
                SELECT * FROM chat_history 
                WHERE user_id = :user_id
                {conversation_filter}
                ORDER BY created_at DESC 
                LIMIT :limit
            """
            params = {'user_id': user_id, 'limit': limit}
            conversation_filter = ""
            if conversation_id:
                conversation_filter = "AND conversation_id = :conversation_id"
                params['conversation_id'] = str(conversation_id)
            
            query = text(base_query.format(conversation_filter=conversation_filter))
            result = await db_session.execute(query, params)
            rows = result.fetchall()
            logger.debug(f"Fetched {len(rows)} chat history entries", extra={"user_id": str(user_id)})
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error("Error fetching chat history", extra={"error": str(e), "user_id": str(user_id)})
            raise DatabaseError(f"Error fetching chat history: {str(e)}")

    def parse_upload(self, file_content: str, file_format: str) -> List[Dict]:
        if file_format not in self.supported_upload_formats:
            raise ValueError(f"Unsupported file format: {file_format}")
        try:
            if file_format == 'csv':
                df = pd.read_csv(StringIO(file_content))
                required_columns = {'date', 'route', 'grade'}
                if not all(col in df.columns for col in required_columns):
                    missing = required_columns - set(df.columns)
                    raise ValueError(f"Missing required columns: {missing}")
                return df.to_dict('records')
            elif file_format == 'json':
                data = pd.read_json(StringIO(file_content))
                return data.to_dict('records')
            else:  # txt format
                df = pd.read_csv(StringIO(file_content), sep='\t')
                return df.to_dict('records')
        except Exception as e:
            raise ValueError(f"Error parsing {file_format} file: {str(e)}")

    def deduplicate_entries(
        self, 
        existing_data: List[Dict], 
        new_data: List[Dict],
        timestamp_field: str = 'date'
    ) -> List[Dict]:
        if not existing_data and not new_data:
            return []
        existing_df = pd.DataFrame(existing_data)
        new_df = pd.DataFrame(new_data)
        if existing_df.empty and not new_df.empty:
            return new_data
        if new_df.empty and not existing_df.empty:
            return existing_data
        combined_df = pd.concat([existing_df, new_df])
        combined_df[timestamp_field] = pd.to_datetime(combined_df[timestamp_field])
        deduplicated_df = (combined_df
            .sort_values(timestamp_field, ascending=False)
            .drop_duplicates(subset=['route'], keep='first')
            .sort_values(timestamp_field)
        )
        deduplicated_df[timestamp_field] = deduplicated_df[timestamp_field].dt.strftime('%Y-%m-%d')
        return deduplicated_df.to_dict('records')

    async def aggregate_all_data(
        self, 
        db_session: AsyncSession,
        user_id: Union[int, UUID, str],
        conversation_id: Optional[int] = None
    ) -> Dict:
        """
        Aggregates all climber data into a unified format.
        
        Args:
            db_session: Database session for this request
            user_id: User ID as UUID, string, or integer
            conversation_id: Optional conversation ID for chat history
        """
        try:
            logger.debug("Starting data aggregation", extra={"user_id": str(user_id)})
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            elif isinstance(user_id, int):
                user_id = UUID(int=user_id, version=4)

            # Log session state
            logger.debug(f"Session transaction active: {db_session.in_transaction()}", extra={"user_id": str(user_id)})

            # Execute queries within the existing transaction
            context = await self.fetch_climber_context(db_session, user_id)
            recent_ticks = await self.fetch_recent_ticks(db_session, user_id)
            performance = await self.fetch_performance_metrics(db_session, user_id)
            chat_history = await self.fetch_chat_history(db_session, user_id, conversation_id)

            if not context:
                logger.debug("No existing context found, calculating defaults", extra={"user_id": str(user_id)})
                # Use selectinload to eagerly load relationships
                stmt = (
                    select(UserTicks)
                    .filter(UserTicks.user_id == user_id)
                    .options(
                        selectinload(UserTicks.performance_pyramid),
                        selectinload(UserTicks.tags)
                    )
                    .order_by(UserTicks.tick_date.desc())
                )
                result = await db_session.execute(stmt)
                ticks = result.scalars().all()
                logger.debug(f"Fetched {len(ticks)} ticks with relationships", extra={"user_id": str(user_id)})
                context = self._calculate_default_context(ticks, user_id)

            aggregated_data = {
                "climber_context": context,
                "recent_ticks": recent_ticks,
                "performance_metrics": performance,
                "chat_history": chat_history,
                "uploads": []
            }
            
            logger.debug("Data aggregation completed successfully", extra={"user_id": str(user_id)})
            return aggregated_data

        except Exception as e:
            logger.error("Error in data aggregation", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": str(user_id)
            })
            raise DatabaseError(f"Error aggregating data: {str(e)}")

    def _calculate_default_context(self, ticks: List[UserTicks], user_id: UUID) -> Dict:
        # Unchanged from previous version
        LEAD_STYLES = {"onsight", "flash", "redpoint", "lead"}

        def get_max_grade(ticks, condition):
            filtered = [t for t in ticks if condition(t)]
            if filtered:
                max_tick = max(filtered, key=lambda t: t.binned_code)
                return max_tick.route_grade
            return None

        if not ticks:
            created_at = datetime.utcnow().isoformat()
            return {
                "id": None,
                "user_id": str(user_id),
                "climbing_goals": None,
                "years_climbing": 0,
                "current_training_description": None,
                "interests": None,
                "injury_information": None,
                "additional_notes": None,
                "total_climbs": 0,
                "favorite_discipline": None,
                "preferred_crag_last_year": None,
                "highest_sport_grade_tried": None,
                "highest_trad_grade_tried": None,
                "highest_boulder_grade_tried": None,
                "highest_grade_sport_sent_clean_on_lead": None,
                "highest_grade_tr_sent_clean": None,
                "highest_grade_trad_sent_clean_on_lead": None,
                "highest_grade_boulder_sent_clean": None,
                "onsight_grade_sport": None,
                "onsight_grade_trad": None,
                "flash_grade_boulder": None,
                "grade_pyramid_sport": [],
                "grade_pyramid_trad": [],
                "grade_pyramid_boulder": [],
                "current_training_frequency": None,
                "typical_session_length": None,
                "typical_session_intensity": None,
                "home_equipment": None,
                "access_to_commercial_gym": False,
                "supplemental_training": None,
                "training_history": None,
                "physical_limitations": None,
                "sleep_score": None,
                "nutrition_score": None,
                "activity_last_30_days": 0,
                "current_projects": None,
                "recent_favorite_routes": None,
                "favorite_angle": None,
                "weakest_angle": None,
                "strongest_angle": None,
                "favorite_energy_type": None,
                "weakest_energy_type": None,
                "strongest_energy_type": None,
                "favorite_hold_types": None,
                "weakest_hold_types": None,
                "strongest_hold_types": None,
                "created_at": created_at,
                "current_info_as_of": created_at,
            }

        today = date.today()
        first_tick = min(ticks, key=lambda t: t.tick_date)
        years_climbing = (today - first_tick.tick_date).days / 365.0
        total_climbs = len(ticks)

        discipline_counts = Counter(t.discipline for t in ticks if t.discipline)
        favorite_discipline = discipline_counts.most_common(1)[0][0].value if discipline_counts else None

        last_year_ticks = [t for t in ticks if (today - t.tick_date).days <= 365]
        crag_counts = Counter(t.location for t in last_year_ticks if t.location)
        preferred_crag_last_year = crag_counts.most_common(1)[0][0] if crag_counts else None

        sport_ticks = [t for t in ticks if t.discipline == ClimbingDiscipline.SPORT]
        trad_ticks = [t for t in ticks if t.discipline == ClimbingDiscipline.TRAD]
        boulder_ticks = [t for t in ticks if t.discipline == ClimbingDiscipline.BOULDER]
        tr_ticks = [t for t in ticks if t.discipline == ClimbingDiscipline.TR]

        highest_sport_grade_tried = get_max_grade(sport_ticks, lambda t: True)
        highest_trad_grade_tried = get_max_grade(trad_ticks, lambda t: True)
        highest_boulder_grade_tried = get_max_grade(boulder_ticks, lambda t: True)

        highest_grade_sport_sent_clean_on_lead = get_max_grade(sport_ticks, lambda t: t.send_bool and t.lead_style and t.lead_style.lower() in LEAD_STYLES)
        highest_grade_trad_sent_clean_on_lead = get_max_grade(trad_ticks, lambda t: t.send_bool and t.lead_style and t.lead_style.lower() in LEAD_STYLES)
        highest_grade_boulder_sent_clean = get_max_grade(boulder_ticks, lambda t: t.send_bool)
        highest_grade_tr_sent_clean = get_max_grade(tr_ticks, lambda t: t.send_bool)

        onsight_grade_sport = get_max_grade(sport_ticks, lambda t: t.send_bool and t.lead_style and t.lead_style.lower() == "onsight")
        onsight_grade_trad = get_max_grade(trad_ticks, lambda t: t.send_bool and t.lead_style and t.lead_style.lower() == "onsight")
        flash_grade_boulder = get_max_grade(boulder_ticks, lambda t: t.send_bool and t.lead_style and t.lead_style.lower() == "flash")

        def build_grade_pyramid(discipline_ticks):
            pyramid_ticks = [t for t in discipline_ticks if t.performance_pyramid]
            if pyramid_ticks:
                sorted_ticks = sorted(pyramid_ticks, key=lambda t: t.binned_code, reverse=True)
                return [
                    {
                        "grade": tick.route_grade,
                        "route_name": tick.route_name,
                        "location": tick.location,
                        "first_sent": tick.performance_pyramid[0].first_sent.isoformat() if tick.performance_pyramid else None,
                        "num_sends": tick.performance_pyramid[0].num_sends if tick.performance_pyramid else None,
                        "num_attempts": tick.performance_pyramid[0].num_attempts if tick.performance_pyramid else None,
                        "days_attempts": tick.performance_pyramid[0].days_attempts if tick.performance_pyramid else None,
                        "crux_angle": tick.performance_pyramid[0].crux_angle.value if tick.performance_pyramid and tick.performance_pyramid[0].crux_angle else None,
                        "crux_energy": tick.performance_pyramid[0].crux_energy.value if tick.performance_pyramid and tick.performance_pyramid[0].crux_energy else None,
                        "tags": [tag.name for tag in tick.tags] if tick.tags else []
                    }
                    for tick in sorted_ticks
                ]
            return []

        grade_pyramid_sport = build_grade_pyramid(sport_ticks)
        grade_pyramid_trad = build_grade_pyramid(trad_ticks)
        grade_pyramid_boulder = build_grade_pyramid(boulder_ticks)

        recent_ticks = [t for t in ticks if (today - t.tick_date).days <= 30]
        activity_last_30_days = len(recent_ticks)

        created_at = datetime.utcnow().isoformat()

        return {
            "id": None,
            "user_id": str(user_id),
            "climbing_goals": None,
            "years_climbing": int(years_climbing),
            "current_training_description": None,
            "interests": None,
            "injury_information": None,
            "additional_notes": None,
            "total_climbs": total_climbs,
            "favorite_discipline": favorite_discipline,
            "preferred_crag_last_year": preferred_crag_last_year,
            "highest_sport_grade_tried": highest_sport_grade_tried,
            "highest_trad_grade_tried": highest_trad_grade_tried,
            "highest_boulder_grade_tried": highest_boulder_grade_tried,
            "highest_grade_sport_sent_clean_on_lead": highest_grade_sport_sent_clean_on_lead,
            "highest_grade_tr_sent_clean": highest_grade_tr_sent_clean,
            "highest_grade_trad_sent_clean_on_lead": highest_grade_trad_sent_clean_on_lead,
            "highest_grade_boulder_sent_clean": highest_grade_boulder_sent_clean,
            "onsight_grade_sport": onsight_grade_sport,
            "onsight_grade_trad": onsight_grade_trad,
            "flash_grade_boulder": flash_grade_boulder,
            "grade_pyramid_sport": grade_pyramid_sport,
            "grade_pyramid_trad": grade_pyramid_trad,
            "grade_pyramid_boulder": grade_pyramid_boulder,
            "current_training_frequency": None,
            "typical_session_length": None,
            "typical_session_intensity": None,
            "home_equipment": None,
            "access_to_commercial_gym": False,
            "supplemental_training": None,
            "training_history": None,
            "physical_limitations": None,
            "sleep_score": None,
            "nutrition_score": None,
            "activity_last_30_days": activity_last_30_days,
            "current_projects": None,
            "recent_favorite_routes": None,
            "favorite_angle": None,
            "weakest_angle": None,
            "strongest_angle": None,
            "favorite_energy_type": None,
            "weakest_energy_type": None,
            "strongest_energy_type": None,
            "favorite_hold_types": None,
            "weakest_hold_types": None,
            "strongest_hold_types": None,
            "created_at": created_at,
            "current_info_as_of": created_at,
        }