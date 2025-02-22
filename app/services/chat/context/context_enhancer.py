from typing import Dict, List, Optional, Union
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
from app.services.utils.grade_service import GradeService, GradingSystem
from app.models.enums import ClimbingDiscipline

class ContextEnhancer:
    """
    Enhances aggregated climber data with trends, relevance scoring, and comparative metrics.
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
        Calculates grade progression over time.
        
        Args:
            ticks: List of climbing attempts/sends
            timeframe_days: Optional timeframe to calculate progression (e.g., 180 for 6 months)
            
        Returns:
            Dictionary containing progression metrics
        """
        if not ticks:
            return {'all_time': 0.0, 'recent': 0.0}

        # Convert ticks to DataFrame for analysis
        df = pd.DataFrame(ticks)
        df['date'] = pd.to_datetime(df['date'])
        
        # Convert grades to numeric codes using GradeService
        grades = df['grade'].tolist()
        # Determine if these are boulder or route grades based on the first grade
        sample_grade = grades[0] if grades else None
        discipline = ClimbingDiscipline.BOULDER if sample_grade and sample_grade.startswith('V') else ClimbingDiscipline.SPORT
        grade_codes = await self.grade_service.convert_grades_to_codes(grades, discipline)
        df['grade_value'] = grade_codes

        # Calculate all-time progression
        df_sorted = df.sort_values('date')
        if len(df_sorted) >= 2:
            days_climbing = (df_sorted['date'].max() - df_sorted['date'].min()).days
            # Calculate average grade improvement per year
            grade_change = df_sorted['grade_value'].max() - df_sorted['grade_value'].min()
            all_time_progression = grade_change * (365 / max(days_climbing, 1))  # Normalize to yearly rate
        else:
            all_time_progression = 0.0

        # Calculate recent progression if timeframe specified
        recent_progression = 0.0
        if timeframe_days:
            cutoff_date = datetime.now() - timedelta(days=timeframe_days)
            recent_df = df[df['date'] >= cutoff_date]
            if len(recent_df) >= 2:
                recent_sorted = recent_df.sort_values('date')
                recent_days = (recent_sorted['date'].max() - recent_sorted['date'].min()).days
                recent_grade_change = recent_sorted['grade_value'].max() - recent_sorted['grade_value'].min()
                recent_progression = recent_grade_change * (365 / max(recent_days, 1))  # Normalize to yearly rate

        return {
            'all_time': round(all_time_progression, 2),
            'recent': round(recent_progression, 2)
        }

    def calculate_training_consistency(self, ticks: List[Dict], days: int = 180) -> float:
        """
        Calculates training consistency score based on climbing frequency.
        
        Args:
            ticks: List of climbing attempts/sends
            days: Number of days to analyze
            
        Returns:
            Consistency score between 0 and 1
        """
        if not ticks:
            return 0.0

        df = pd.DataFrame(ticks)
        df['date'] = pd.to_datetime(df['date'])
        
        # Focus on recent period
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_df = df[df['date'] >= cutoff_date]
        
        if len(recent_df) == 0:
            return 0.0

        # Calculate unique climbing days and frequency
        unique_days = recent_df['date'].dt.date.nunique()
        expected_sessions = days / 7 * 3  # Assuming 3 sessions per week is optimal
        consistency = min(1.0, unique_days / expected_sessions)
        
        return round(consistency, 2)

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

        df = pd.DataFrame(ticks)
        df['date'] = pd.to_datetime(df['date'])
        
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

    async def calculate_goal_progress(
        self, 
        current_grade: str,
        goal_grade: str,
        deadline: Optional[datetime] = None
    ) -> Dict[str, Union[float, str]]:
        """
        Calculates progress towards climbing goals.
        
        Args:
            current_grade: Current climbing grade
            goal_grade: Target climbing grade
            deadline: Optional deadline for the goal
            
        Returns:
            Dictionary with goal progress metrics
        """
        # Determine discipline based on grade format
        discipline = ClimbingDiscipline.BOULDER if current_grade.startswith('V') else ClimbingDiscipline.SPORT
        
        # Convert grades to numeric codes - do both conversions in one call
        grade_codes = await self.grade_service.convert_grades_to_codes([current_grade, goal_grade], discipline)
        current_value = grade_codes[0]
        goal_value = grade_codes[1]
        
        if current_value >= goal_value:
            return {
                'progress': 1.0,
                'status': 'achieved',
                'time_remaining': self._format_time_remaining(deadline) if deadline else None
            }
            
        total_grades = goal_value - current_value
        progress = 0.0 if total_grades == 0 else current_value / goal_value
        
        status = 'on_track'
        if deadline:
            days_remaining = (deadline - datetime.now()).days
            if days_remaining < 0:
                status = 'overdue'
            elif progress < (1 - (days_remaining / 365)):  # Simple linear progress expectation
                status = 'behind'
                
        return {
            'progress': round(progress, 2),
            'status': status,
            'time_remaining': self._format_time_remaining(deadline) if deadline else None
        }

    def add_relevance_scores(
        self,
        query: str,
        context_data: Dict
    ) -> Dict[str, float]:
        """
        Assigns relevance scores to different context sections based on the query.
        
        Args:
            query: User's question or request
            context_data: Aggregated context data
            
        Returns:
            Dictionary with relevance scores for each section
        """
        # Define keyword mappings for different aspects
        keyword_mappings = {
            'training': {'training', 'practice', 'drill', 'exercise', 'workout', 'improve', 'progress', 'routine', 'regimen', 'schedule'},
            'performance': {'grade', 'send', 'project', 'achievement', 'climb', 'attempt', 'complete', 'success'},
            'technique': {'beta', 'movement', 'sequence', 'footwork', 'grip', 'hold', 'body', 'position', 'dynamic'},
            'goals': {'goal', 'target', 'aim', 'objective', 'plan', 'future', 'achieve', 'reach'},
            'health': {'injury', 'recovery', 'rest', 'nutrition', 'sleep', 'pain', 'fatigue', 'energy'}
        }
        
        # Initialize scores
        scores = defaultdict(float)
        query_words = set(query.lower().split())
        
        # Calculate base scores from keyword matches
        for aspect, keywords in keyword_mappings.items():
            matches = len(keywords & query_words)
            scores[aspect] = min(1.0, matches * 0.3)  # 0.3 weight per keyword match, max 1.0
            
            # Add partial matches (e.g., "training" matches "train")
            for word in query_words:
                for keyword in keywords:
                    if word in keyword or keyword in word:
                        scores[aspect] += 0.2  # Lower weight for partial matches
            
        # Adjust scores based on context data
        if context_data.get('climber_context', {}).get('injury_status'):
            scores['health'] += 0.3
            
        if context_data.get('performance_metrics', {}).get('grade_progression', 0) < 0:
            scores['training'] += 0.2
            
        # Normalize scores
        max_score = max(scores.values()) if scores else 1.0
        normalized_scores = {
            k: round(min(1.0, v / max_score), 2) if max_score > 0 else 0 
            for k, v in scores.items()
        }
        
        return normalized_scores

    async def enhance_context(
        self,
        raw_data: Dict,
        query: Optional[str] = None
    ) -> Dict:
        """
        Main method to enhance raw context data with trends and insights.
        
        Args:
            raw_data: Aggregated raw context data
            query: Optional user query for relevance scoring
            
        Returns:
            Enhanced context data
        """
        enhanced_data = raw_data.copy()
        
        # Add grade progression trends
        ticks = raw_data.get('recent_ticks', [])
        enhanced_data['trends'] = {
            'grade_progression': await self.calculate_grade_progression(ticks, 180),  # 6 months
            'training_consistency': self.calculate_training_consistency(ticks),
            'activity_levels': self.calculate_activity_levels(ticks)
        }
        
        # Add goal progress if available
        context = raw_data.get('climber_context', {})
        if 'current_grade' in context and 'goal_grade' in context:
            enhanced_data['goals'] = {
                'progress': await self.calculate_goal_progress(
                    context['current_grade'],
                    context['goal_grade'],
                    context.get('goal_deadline')
                )
            }
            
        # Add relevance scores only if query is provided and not empty
        if query and query.strip():
            enhanced_data['relevance'] = self.add_relevance_scores(query, raw_data)
        elif 'relevance' in enhanced_data:
            del enhanced_data['relevance']  # Remove relevance if it exists but no query provided
            
        return enhanced_data

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
