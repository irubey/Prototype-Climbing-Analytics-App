from typing import Dict, List, Optional, Union
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
from app.services.utils.grade_service import GradeService, GradingSystem
from app.models.enums import ClimbingDiscipline
import logging

logger = logging.getLogger(__name__)

class ContextEnhancer:
    """
    Enhances aggregated climber data with trends and comparative metrics.
    Processes raw data to add insights and goal-oriented structuring.
    """
    
    def __init__(self):
        self.grade_service = GradeService.get_instance()

    async def calculate_grade_progression(
        self,
        ticks: List[Dict],
        timeframe_days: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculates grade progression over time using binned_code values.
        
        Args:
            ticks: List of climbing attempts/sends
            timeframe_days: Optional timeframe to calculate progression (e.g., 180 for 6 months)
            
        Returns:
            Dictionary containing progression metrics
        """
        if not ticks:
            return {'all_time': 0.0, 'recent': 0.0}

        try:
            # Convert ticks to DataFrame for analysis
            df = pd.DataFrame(ticks)
            # Use tick_date instead of date
            df['date'] = pd.to_datetime(df['tick_date'])
            
            # Filter out ticks without binned_code
            df = df[df['binned_code'].notna()]
            
            if len(df) < 2:
                return {'all_time': 0.0, 'recent': 0.0}

            # Calculate all-time progression
            df_sorted = df.sort_values('date')
            days_climbing = (df_sorted['date'].max() - df_sorted['date'].min()).days
            # Calculate average grade improvement per year
            grade_change = df_sorted['binned_code'].max() - df_sorted['binned_code'].min()
            all_time_progression = grade_change * (365 / max(days_climbing, 1))  # Normalize to yearly rate

            # Calculate recent progression if timeframe specified
            recent_progression = 0.0
            if timeframe_days:
                cutoff_date = datetime.now() - timedelta(days=timeframe_days)
                recent_df = df[df['date'] >= cutoff_date]
                if len(recent_df) >= 2:
                    recent_sorted = recent_df.sort_values('date')
                    recent_days = (recent_sorted['date'].max() - recent_sorted['date'].min()).days
                    recent_grade_change = recent_sorted['binned_code'].max() - recent_sorted['binned_code'].min()
                    recent_progression = recent_grade_change * (365 / max(recent_days, 1))  # Normalize to yearly rate

            return {
                'all_time': round(all_time_progression, 2),
                'recent': round(recent_progression, 2)
            }
        except Exception as e:
            logger.error(f"Error calculating grade progression: {str(e)}", extra={
                "error_type": type(e).__name__,
                "ticks_count": len(ticks)
            })
            return {'all_time': 0.0, 'recent': 0.0}


    def calculate_activity_levels(self, ticks: List[Dict]) -> Dict[str, float]:
        """
        Calculates activity levels for different timeframes.
        
        Args:
            ticks: List of climbing attempts/sends
            
        Returns:
            Dictionary with activity metrics
        """
        if not ticks:
            return {'weekly': 0, 'monthly': 0}

        try:
            df = pd.DataFrame(ticks)
            df['date'] = pd.to_datetime(df['tick_date'])
            
            # Calculate weekly and monthly averages
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            weekly_sessions = len(df[df['date'] >= week_ago])
            monthly_sessions = len(df[df['date'] >= month_ago]) / 4  # Average per week

            return {
                'weekly': round(weekly_sessions, 1),
                'monthly': round(monthly_sessions, 1)
            }
        except Exception as e:
            logger.error(f"Error calculating activity levels: {str(e)}", extra={
                "error_type": type(e).__name__,
                "ticks_count": len(ticks)
            })
            return {'weekly': 0, 'monthly': 0}
     

    async def enhance_context(
        self,
        raw_data: Dict,
        query: Optional[str] = None
    ) -> Dict:
        """
        Main method to enhance raw context data with trends and insights.
        """
        try:
            return raw_data
            
        except Exception as e:
            logger.error("Error enhancing context", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "raw_data_keys": list(raw_data.keys()) if raw_data else None
            })
            return raw_data

    def _format_time_remaining(self, deadline: Optional[datetime]) -> Optional[str]:
        """Format the time remaining until the deadline in a human-readable format."""
        if not deadline:
            return None
            
        days_remaining = (deadline - datetime.now()).days
        if days_remaining < 0:
            return 'overdue'
        elif days_remaining == 0:
            return 'today'
        elif days_remaining == 1:
            return 'tomorrow'
        elif days_remaining < 7:
            return f'{days_remaining} days'
        elif days_remaining < 30:
            weeks = days_remaining // 7
            return f'{weeks} weeks'
        else:
            months = days_remaining // 30
            return f'{months} months'
