from typing import Dict, List, Optional
from datetime import datetime
import json

class UnifiedFormatter:
    """
    Formats enhanced context data into a unified JSON format with human-readable summaries
    and structured sections optimized for AI model consumption.
    """

    def __init__(self):
        self.context_version = "1.0"
        self.experience_levels = {
            'beginner': {'years': 0, 'grade': 'V3'},
            'intermediate': {'years': 2, 'grade': 'V5'},
            'advanced': {'years': 4, 'grade': 'V8'}
        }

    def determine_experience_level(self, context_data: Dict) -> str:
        """
        Determines climber experience level based on years climbing and highest grade.
        
        Args:
            context_data: Dictionary containing climber context
            
        Returns:
            Experience level string ('beginner', 'intermediate', or 'advanced')
        """
        climber_context = context_data.get('climber_context', {})
        years_climbing = climber_context.get('years_climbing', 0)
        highest_grade = climber_context.get('highest_boulder_grade', 'V0')
        
        # Convert grade to numeric value for comparison
        grade_value = int(highest_grade.replace('V', '')) if highest_grade.startswith('V') else 0
        
        if (years_climbing >= self.experience_levels['advanced']['years'] or 
            grade_value >= int(self.experience_levels['advanced']['grade'].replace('V', ''))):
            return 'advanced'
        elif (years_climbing >= self.experience_levels['intermediate']['years'] or 
              grade_value >= int(self.experience_levels['intermediate']['grade'].replace('V', ''))):
            return 'intermediate'
        else:
            return 'beginner'

    def generate_summary(self, context_data: Dict, experience_level: str) -> str:
        """
        Generates a human-readable summary of the climber's context.
        
        Args:
            context_data: Enhanced context data
            experience_level: Determined experience level
            
        Returns:
            Human-readable summary string
        """
        climber_context = context_data.get('climber_context', {})
        trends = context_data.get('trends', {})
        goals = context_data.get('goals', {})
        
        # Basic information
        summary_parts = []
        years_climbing = climber_context.get('years_climbing', 0)
        summary_parts.append(
            f"{'An experienced' if years_climbing > 3 else 'A'} {experience_level} climber "
            f"with {years_climbing} years of experience"
        )
        
        # Current level and progression
        highest_grade = climber_context.get('highest_boulder_grade', 'V0')
        grade_progression = trends.get('grade_progression', {})
        if grade_progression.get('recent', 0) > 0:
            summary_parts.append(
                f"currently climbing {highest_grade} with positive grade progression"
            )
        else:
            summary_parts.append(f"currently climbing {highest_grade}")
        
        # Training consistency
        consistency = trends.get('training_consistency', 0)
        if consistency > 0.8:
            summary_parts.append("maintaining very consistent training")
        elif consistency > 0.5:
            summary_parts.append("training regularly")
        
        # Goals
        goal_grade = climber_context.get('goal_grade')
        if goal_grade:
            goal_progress = goals.get('progress', {'progress': 0.0, 'status': 'on_track', 'time_remaining': None})
            if not isinstance(goal_progress, dict):
                # Convert old format to new format
                goal_progress = {
                    'progress': float(goal_progress),
                    'status': goals.get('status', 'on_track'),
                    'time_remaining': goals.get('time_remaining')
                }
            status = goal_progress.get('status', 'on_track')
            time_remaining = goal_progress.get('time_remaining')
            
            goal_text = f"working towards {goal_grade}"
            if time_remaining:
                goal_text += f" with {time_remaining} remaining"
                
            if status == 'on_track':
                summary_parts.append(goal_text)
            elif status == 'behind':
                summary_parts.append(f"working to get back on track for {goal_text}")
        
        # Health status
        injury_status = climber_context.get('injury_status')
        if injury_status:
            summary_parts.append(f"currently managing a {injury_status} injury")
        
        return '. '.join(summary_parts) + '.'

    def format_performance_data(self, context_data: Dict) -> Dict:
        """
        Formats performance-related data into a structured section.
        
        Args:
            context_data: Enhanced context data
            
        Returns:
            Structured performance data
        """
        trends = context_data.get('trends', {})
        performance = {
            'grade_progression': trends.get('grade_progression', {}),
            'training_consistency': trends.get('training_consistency', 0),
            'activity_levels': trends.get('activity_levels', {})
        }
        
        # Add comparative metrics if available, but preserve grade_progression from trends
        if 'performance_metrics' in context_data:
            metrics = context_data['performance_metrics'].copy()
            if 'grade_progression' in metrics:
                metrics['historical_grade_progression'] = metrics.pop('grade_progression')
            performance.update(metrics)
            
        return performance

    def format_training_data(self, context_data: Dict) -> Dict:
        """
        Formats training-related data into a structured section.
        
        Args:
            context_data: Enhanced context data
            
        Returns:
            Structured training data
        """
        climber_context = context_data.get('climber_context', {})
        return {
            'frequency': climber_context.get('training_frequency', 'unknown'),
            'preferred_styles': climber_context.get('preferred_styles', []),
            'strengths': climber_context.get('strengths', []),
            'weaknesses': climber_context.get('weaknesses', []),
            'recent_focus': climber_context.get('training_focus', 'general')
        }

    def format_health_data(self, context_data: Dict) -> Dict:
        """
        Formats health-related data into a structured section.
        
        Args:
            context_data: Enhanced context data
            
        Returns:
            Structured health data
        """
        climber_context = context_data.get('climber_context', {})
        return {
            'injury_status': climber_context.get('injury_status'),
            'recovery_protocol': climber_context.get('recovery_protocol'),
            'energy_levels': climber_context.get('energy_levels', 'normal'),
            'sleep_quality': climber_context.get('sleep_quality', 'normal')
        }

    def format_context(
        self, 
        enhanced_data: Dict,
        query: Optional[str] = None
    ) -> Dict:
        """
        Main method to format enhanced context data into the final unified format.
        
        Args:
            enhanced_data: Enhanced context data
            query: Optional user query for relevance scoring
            
        Returns:
            Formatted context in unified JSON format
        """
        # Determine experience level
        experience_level = self.determine_experience_level(enhanced_data)
        
        # Generate human-readable summary
        summary = self.generate_summary(enhanced_data, experience_level)
        
        # Structure the formatted context
        formatted_context = {
            "context_version": self.context_version,
            "summary": summary,
            "profile": {
                "experience_level": experience_level,
                "years_climbing": enhanced_data.get('climber_context', {}).get('years_climbing', 0),
                "preferred_styles": enhanced_data.get('climber_context', {}).get('preferred_styles', [])
            },
            "performance": self.format_performance_data(enhanced_data),
            "training": self.format_training_data(enhanced_data),
            "health": self.format_health_data(enhanced_data),
            "goals": enhanced_data.get('goals', {}),
            "recent_activity": {
                "ticks": enhanced_data.get('recent_ticks', [])[:10],  # Last 10 climbs
                "chat_history": enhanced_data.get('chat_history', [])
            }
        }
        
        # Add relevance scores if query provided
        if query and 'relevance' in enhanced_data:
            formatted_context['relevance'] = enhanced_data['relevance']
            
        return formatted_context

    def to_json(self, formatted_context: Dict) -> str:
        """
        Converts formatted context to JSON string.
        
        Args:
            formatted_context: Formatted context dictionary
            
        Returns:
            JSON string representation
        """
        return json.dumps(formatted_context, default=str, indent=2)
