from collections import Counter
from sqlalchemy import func, desc
from app.models import UserTicks, SportPyramid, TradPyramid, BoulderPyramid
from datetime import datetime

class AnalyticsService:
    def __init__(self, db):
        self.db = db
        
    def get_base_volume_metrics(self, userId: int = None):
        """Get base volume metrics for a user."""
        if not userId:
            raise ValueError("userId must be provided")
            

        # Query user ticks
        user_ticks = UserTicks.query.filter_by(userId=userId).all()

        
        if not user_ticks:
            return {}

        # Calculate metrics
        total_pitches = sum(tick.pitches or 0 for tick in user_ticks)
        unique_locations = len(set(tick.location for tick in user_ticks if tick.location))
        total_days = len(set(tick.tick_date for tick in user_ticks if tick.tick_date))
        
        # Get most visited location
        location_counts = {}
        for tick in user_ticks:
            if tick.location:
                location_counts[tick.location] = location_counts.get(tick.location, 0) + 1
        favorite_location = max(location_counts.items(), key=lambda x: x[1])[0] if location_counts else None

        return {
            "total_pitches": total_pitches,
            "unique_locations": unique_locations,
            "days_outside": total_days,
            "favorite_area": favorite_location
        }

    def get_performance_metrics(self, userId: int = None):
        """Get performance metrics for a user."""
        if not userId:
            raise ValueError("userId must be provided")
            
        # Query highest grades for each discipline
        sport_highest = SportPyramid.query.filter_by(userId=userId).order_by(SportPyramid.binned_code.desc()).first()
        trad_highest = TradPyramid.query.filter_by(userId=userId).order_by(TradPyramid.binned_code.desc()).first()
        boulder_highest = BoulderPyramid.query.filter_by(userId=userId).order_by(BoulderPyramid.binned_code.desc()).first()

        # Get latest sends from all pyramids
        latest_sends = []
        
        # Get recent sport sends
        sport_sends = SportPyramid.query.filter_by(userId=userId)\
            .order_by(SportPyramid.tick_date.desc())\
            .limit(5).all()
        for send in sport_sends:
            latest_sends.append({
                "route_name": send.route_name,
                "binned_grade": send.binned_grade,
                "location": send.location,
                "num_attempts": send.num_attempts,
                "discipline": "Sport",
                "tick_date": send.tick_date
            })

        # Get recent trad sends
        trad_sends = TradPyramid.query.filter_by(userId=userId)\
            .order_by(TradPyramid.tick_date.desc())\
            .limit(5).all()
        for send in trad_sends:
            latest_sends.append({
                "route_name": send.route_name,
                "binned_grade": send.binned_grade,
                "location": send.location,
                "num_attempts": send.num_attempts,
                "discipline": "Trad",
                "tick_date": send.tick_date
            })

        # Get recent boulder sends
        boulder_sends = BoulderPyramid.query.filter_by(userId=userId)\
            .order_by(BoulderPyramid.tick_date.desc())\
            .limit(5).all()
        for send in boulder_sends:
            latest_sends.append({
                "route_name": send.route_name,
                "binned_grade": send.binned_grade,
                "location": send.location,
                "num_attempts": send.num_attempts,
                "discipline": "Boulder",
                "tick_date": send.tick_date
            })

        # Sort all sends by date and take the 5 most recent
        latest_sends.sort(key=lambda x: x['tick_date'] if x['tick_date'] else datetime.min, reverse=True)
        latest_sends = latest_sends[:5]

        return {
            "highest_sport_grade": sport_highest.binned_grade if sport_highest else "-",
            "highest_trad_grade": trad_highest.binned_grade if trad_highest else "-",
            "highest_boulder_grade": boulder_highest.binned_grade if boulder_highest else "-",
            "latest_sends": latest_sends
        }

    def get_all_metrics(self, userId: int = None):
        """Get all metrics for a user."""
        if not userId:
            raise ValueError("userId must be provided")
            

        base_metrics = self.get_base_volume_metrics(userId=userId)
        performance_metrics = self.get_performance_metrics(userId=userId)
        
        return {**base_metrics, **performance_metrics} 