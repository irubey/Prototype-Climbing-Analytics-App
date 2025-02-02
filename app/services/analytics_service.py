from collections import Counter
from sqlalchemy import func, desc, and_
from app.models import UserTicks, PerformancePyramid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, db):
        self.db = db
        
    def get_base_volume_metrics(self, user_id: int = None):
        """Get base volume metrics for a user."""
        if not user_id:
            raise ValueError("user_id must be provided")
            
        try:
            # Query user ticks
            user_ticks = UserTicks.query.filter_by(user_id=user_id).all()
            
            if not user_ticks:
                logger.warning(f"No ticks found for user: {user_id}")
                return {}

            # Calculate metrics
            total_pitches = sum(tick.pitches or 0 for tick in user_ticks)
            unique_locations = len(set(tick.location_raw for tick in user_ticks if tick.location_raw))
            total_days = len(set(tick.tick_date for tick in user_ticks if tick.tick_date))
            
            # Get most visited location
            location_counts = Counter(tick.location for tick in user_ticks if tick.location)
            favorite_location = location_counts.most_common(1)[0][0] if location_counts else None

            return {
                "total_pitches": total_pitches,
                "unique_locations": unique_locations,
                "days_outside": total_days,
                "favorite_area": favorite_location,
            }
            
        except Exception as e:
            logger.error(f"Error getting base volume metrics: {str(e)}")
            return {}

    def get_performance_metrics(self, user_id: int = None):
        """Get performance metrics for a user."""
        if not user_id:
            raise ValueError("user_id must be provided")
            
        try:
            # Get ticks that are counted in performance pyramid by joining tables
            sends = (self.db.session.query(UserTicks, PerformancePyramid)
                    .join(PerformancePyramid, UserTicks.id == PerformancePyramid.tick_id)
                    .filter(UserTicks.user_id == user_id)
                    .order_by(PerformancePyramid.send_date.desc())
                    .all())
            
            if not sends:
                logger.warning(f"No performance pyramid entries found for user: {user_id}")
                return {}

            # Calculate top 3 disciplines
            discipline_counts = Counter(send[0].discipline for send in sends)
            top_3_disciplines = sorted(discipline_counts.keys(), key=lambda x: discipline_counts[x], reverse=True)[:3]
            
            # Calculate highest grades by discipline
            highest_grades = {}
            for discipline in top_3_disciplines:
                discipline_sends = [send[0] for send in sends if send[0].discipline == discipline]
                if discipline_sends:
                    highest_grades[str(discipline.value)] = max(send.binned_grade for send in discipline_sends)
                else:
                    highest_grades[str(discipline.value)] = "-"
            
            # Get latest performance pyramid entries
            latest_hard_sends = sends[:10]
            
            # Format latest sends
            formatted_hard_sends = [{
                "route_name": send[0].route_name,
                "route_grade": send[0].route_grade,
                "location": send[0].location,
                "send_date": send[1].send_date,
                "discipline": str(send[0].discipline.value),
                "route_url": send[0].route_url,
                "lead_style": send[0].lead_style,
            } for send in latest_hard_sends]

            return {
                "highest_grades": highest_grades,
                "latest_hard_sends": formatted_hard_sends,
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}", exc_info=True)
            return {}

    def get_all_metrics(self, user_id: int = None):
        """Get all metrics for a user."""
        if not user_id:
            raise ValueError("user_id must be provided")
            
        try:
            base_metrics = self.get_base_volume_metrics(user_id=user_id)
            performance_metrics = self.get_performance_metrics(user_id=user_id)
            
            # Default values for empty metrics
            default_metrics = {
                "total_pitches": 0,
                "unique_locations": 0,
                "days_outside": 0,
                "favorite_area": "None",
                "highest_grades": {},
                "latest_hard_sends": []
            }
            
            # Combine metrics with defaults and add timestamp
            metrics = {
                **default_metrics,
                **base_metrics, 
                **performance_metrics,
                "last_updated": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully generated metrics for user: {user_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting all metrics: {str(e)}")
            return default_metrics 