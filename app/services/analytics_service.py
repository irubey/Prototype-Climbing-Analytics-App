from collections import Counter
from sqlalchemy import func, desc
from app.models import UserTicks, SportPyramid, TradPyramid, BoulderPyramid
from datetime import datetime

class AnalyticsService:
    def __init__(self, db):
        self.db = db

    def calculate_total_vertical(self, user_ticks):
        """Calculate total vertical feet using the same logic as totalVert.js."""
        # 1. Transform data (create new objects to avoid modifying originals)
        transformed_ticks = []
        for tick in user_ticks:
            try:
                float(tick.pitches)  # This matches JS isNaN behavior
                has_valid_pitches = True
            except (TypeError, ValueError):
                has_valid_pitches = False

            if has_valid_pitches or tick.length_category == "multipitch":
                transformed_ticks.append({
                    'date': tick.tick_date,
                    'length': None if tick.length == 0 else tick.length,
                    'pitches': 1 if tick.length_category == "multipitch" else tick.pitches,
                    'length_category': tick.length_category,
                    'season_category': tick.season_category[:-6] if tick.season_category else ''
                })

        # 2. Calculate daily averages for all routes with valid length
        daily_averages = {}
        for tick in transformed_ticks:
            if tick['length'] is not None:
                date_str = tick['date'].strftime('%Y-%m-%d')
                if date_str not in daily_averages:
                    daily_averages[date_str] = {"sum": tick['length'], "count": 1}
                else:
                    daily_averages[date_str]["sum"] += tick['length']
                    daily_averages[date_str]["count"] += 1

        # Convert sums to averages
        for date_str in daily_averages:
            daily_averages[date_str] = daily_averages[date_str]["sum"] / daily_averages[date_str]["count"]

        # 3. Calculate vertical feet by date
        vertical_map = {}
        for tick in transformed_ticks:
            date_str = tick['date'].strftime('%Y-%m-%d')
            map_key = f"{date_str}_{tick['season_category']}"
            
            if tick['length']:
                vertical = tick['length'] if tick['length_category'] == "multipitch" else tick['length'] * tick['pitches']
            else:
                daily_avg = daily_averages.get(date_str)
                vertical = (daily_avg if daily_avg is not None else 60) * tick['pitches']

            if map_key not in vertical_map:
                vertical_map[map_key] = {
                    'total': vertical or 0,
                    'season_category': tick['season_category']
                }
            else:
                vertical_map[map_key]['total'] += vertical or 0

        # 4. Sum all verticals and return
        return sum(v['total'] for v in vertical_map.values())

    def get_base_volume_metrics(self, username):
        """Calculate base volume metrics from UserTicks."""
        user_ticks = UserTicks.query.filter_by(username=username).all()
        
        # Calculate total pitches
        total_pitches = sum(tick.pitches or 1 for tick in user_ticks)
        
        # Calculate total vertical feet using the new method
        total_vertical_ft = int(self.calculate_total_vertical(user_ticks))
        
        # Get unique locations
        unique_locations = len(set(tick.location for tick in user_ticks if tick.location))
        
        # Find favorite area (most common location)
        locations = [tick.location for tick in user_ticks if tick.location]
        favorite_area = Counter(locations).most_common(1)[0][0] if locations else "-"
        
        # Calculate unique dates (days outside)
        unique_dates = len(set(tick.tick_date for tick in user_ticks if tick.tick_date))
        
        return {
            "total_pitches": total_pitches,
            "total_vertical_ft": total_vertical_ft,
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
            'num_attempts': "Flash/Onsight" if (send.num_attempts or 1) == 1 else f"{send.num_attempts} attempts",
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