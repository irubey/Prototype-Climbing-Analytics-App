from collections import Counter
from sqlalchemy import func, desc
from app.models import UserTicks, SportPyramid, TradPyramid, BoulderPyramid
from datetime import datetime

class AnalyticsService:
    def __init__(self, db):
        self.db = db
        
    def get_base_volume_metrics(self, username):
        """Calculate base volume metrics from UserTicks."""
        user_ticks = UserTicks.query.filter_by(username=username).all()
        
        # Calculate total pitches
        total_pitches = sum(tick.pitches or 1 for tick in user_ticks)

        # Get unique locations
        unique_locations = len(set(tick.location for tick in user_ticks if tick.location))
        
        # Find favorite area (most common location)
        locations = [tick.location for tick in user_ticks if tick.location]
        favorite_area = Counter(locations).most_common(1)[0][0] if locations else "-"
        
        # Calculate unique dates (days outside)
        unique_dates = len(set(tick.tick_date for tick in user_ticks if tick.tick_date))
        
        return {
            "total_pitches": total_pitches,
            "unique_locations": unique_locations,
            "favorite_area": favorite_area,
            "days_outside": unique_dates
        }

    def get_performance_metrics(self, username):
        """Calculate performance metrics from pyramid data."""
        # Get highest grades for each discipline
        sport_highest = SportPyramid.query.filter_by(username=username)\
            .order_by(desc(SportPyramid.binned_code)).first()
        trad_highest = TradPyramid.query.filter_by(username=username)\
            .order_by(desc(TradPyramid.binned_code)).first()
        boulder_highest = BoulderPyramid.query.filter_by(username=username)\
            .order_by(desc(BoulderPyramid.binned_code)).first()

        # Get 6 latest sends across all disciplines
        sport_sends = SportPyramid.query.filter_by(username=username)\
            .order_by(desc(SportPyramid.tick_date)).limit(6).all()
        trad_sends = TradPyramid.query.filter_by(username=username)\
            .order_by(desc(TradPyramid.tick_date)).limit(6).all()
        boulder_sends = BoulderPyramid.query.filter_by(username=username)\
            .order_by(desc(BoulderPyramid.tick_date)).limit(6).all()

        # Combine and sort all sends by date
        all_sends = sorted(
            sport_sends + trad_sends + boulder_sends,
            key=lambda x: x.tick_date,
            reverse=True
        )[:6]

        # Format sends for display
        latest_sends = [{
            'route_name': send.route_name,
            'binned_grade': send.binned_grade,
            'location': send.location,
            'num_attempts': (
                "Flash/Onsight" if send.lead_style == "Flash" or send.lead_style == "Onsight"
                else "Flash/Onsight" if send.num_attempts == 1 and send.lead_style not in ['Redpoint', 'Pinkpoint']
                else f"{send.num_attempts} attempts - redpoint" if send.num_attempts and send.num_attempts > 1
                else "Redpoint - unknown attempts" if send.lead_style in ['Redpoint', 'Pinkpoint']
                else "Unknown style"
            ),
            'discipline': send.discipline
        } for send in all_sends]

        return {
            "highest_sport_grade": sport_highest.binned_grade if sport_highest else "-",
            "highest_trad_grade": trad_highest.binned_grade if trad_highest else "-",
            "highest_boulder_grade": boulder_highest.binned_grade if boulder_highest else "-",
            "latest_sends": latest_sends
        }

    def get_all_metrics(self, username):
        """Get all metrics for a user."""
        base_metrics = self.get_base_volume_metrics(username)
        performance_metrics = self.get_performance_metrics(username)
        
        return {**base_metrics, **performance_metrics} 