# Formats and assembles user data, metrics, and custom instructions

from typing import Dict, Any, Optional
from dataclasses import dataclass
from ..grade_processor import GradeProcessor

@dataclass
class FormattedContext:
    """Container for formatted context data used by AI models"""
    conversational_context: str  # Human-readable format for V3
    structured_context: Dict[str, Any]  # JSON structure for R1

class ContextFormatter:
    """Formats user data and metrics for AI model consumption"""
    
    def __init__(self):
        self.grade_processor = GradeProcessor()

    def format_climber_context(self, climber_summary: Any) -> FormattedContext:
        """Creates both conversational and structured context from climber summary"""
        conv_context = self._create_conversational_context(climber_summary)
        struct_context = self._create_structured_context(climber_summary)
        
        return FormattedContext(
            conversational_context=conv_context,
            structured_context=struct_context
        )

    def _create_conversational_context(self, summary: Any) -> str:
        """Creates human-readable context for V3 model"""
        context_parts = []
        
        # Core climbing profile
        exp_text = f"{summary.years_climbing_outside} years" if summary.years_climbing_outside else "unknown time"
        context_parts.append(
            f"The climber has been climbing outside for {exp_text} and primarily focuses on "
            f"{summary.favorite_discipline.value if summary.favorite_discipline else 'various types of'} "
            f"climbing. Their highest grades attempted are: Sport: {summary.highest_sport_grade_tried}, "
            f"Trad: {summary.highest_trad_grade_tried}, Boulder: {summary.highest_boulder_grade_tried}."
        )

        # Clean sends and onsight/flash grades
        send_grades = []
        if summary.highest_grade_sport_sent_clean_on_lead:
            send_grades.append(f"Sport lead: {summary.highest_grade_sport_sent_clean_on_lead}")
        if summary.highest_grade_trad_sent_clean_on_lead:
            send_grades.append(f"Trad lead: {summary.highest_grade_trad_sent_clean_on_lead}")
        if summary.highest_grade_boulder_sent_clean:
            send_grades.append(f"Boulder: {summary.highest_grade_boulder_sent_clean}")
        
        if send_grades:
            context_parts.append(f"Clean sends - {', '.join(send_grades)}.")

        flash_grades = []
        if summary.onsight_grade_sport:
            flash_grades.append(f"Sport onsight: {summary.onsight_grade_sport}")
        if summary.onsight_grade_trad:
            flash_grades.append(f"Trad onsight: {summary.onsight_grade_trad}")
        if summary.flash_grade_boulder:
            flash_grades.append(f"Boulder flash: {summary.flash_grade_boulder}")
            
        if flash_grades:
            context_parts.append(f"Flash/Onsight grades - {', '.join(flash_grades)}.")

        # Training context
        training_parts = []
        if summary.training_frequency:
            training_parts.append(f"trains {summary.training_frequency} times per week")
        if summary.typical_session_length:
            training_parts.append(f"with {summary.typical_session_length.value} sessions")
        if summary.has_hangboard:
            training_parts.append("has access to a hangboard")
        if summary.has_home_wall:
            training_parts.append("has a home wall")
        if summary.goes_to_gym:
            training_parts.append("climbs in a gym")
            
        if training_parts:
            context_parts.append(f"Training habits: {', '.join(training_parts)}.")

        # Style preferences and strengths
        style_parts = []
        if summary.favorite_angle:
            style_parts.append(f"prefers {summary.favorite_angle.value} climbing")
        if summary.strongest_energy_type:
            style_parts.append(f"excels at {summary.strongest_energy_type.value} climbing")
        if summary.strongest_hold_types:
            style_parts.append(f"strongest on {summary.strongest_hold_types.value}")
            
        if style_parts:
            context_parts.append(f"Style preferences: {', '.join(style_parts)}.")

        # Health and lifestyle
        health_parts = []
        if summary.sleep_score:
            health_parts.append(f"sleep quality is {summary.sleep_score.value}")
        if summary.nutrition_score:
            health_parts.append(f"nutrition is {summary.nutrition_score.value}")
        if summary.current_injuries:
            health_parts.append(f"current injuries: {summary.current_injuries}")
            
        if health_parts:
            context_parts.append(f"Health status: {', '.join(health_parts)}.")

        # Recent activity and goals
        if summary.sends_last_30_days is not None:
            context_parts.append(f"Has logged {summary.sends_last_30_days} sends in the last 30 days.")
        
        if summary.climbing_goals:
            context_parts.append(f"Current goals: {summary.climbing_goals}")

        return " ".join(context_parts)

    def _create_structured_context(self, summary: Any) -> Dict[str, Any]:
        """Creates JSON structure for R1 advanced reasoning"""
        return {
            "climber_profile": {
                "experience": {
                    "years_outside": summary.years_climbing_outside,
                    "primary_discipline": summary.favorite_discipline.value if summary.favorite_discipline else None,
                    "total_climbs": summary.total_climbs,
                    "recent_activity": summary.sends_last_30_days
                },
                "grades": {
                    "sport": {
                        "highest_tried": summary.highest_sport_grade_tried,
                        "highest_clean_lead": summary.highest_grade_sport_sent_clean_on_lead,
                        "onsight": summary.onsight_grade_sport,
                        "pyramid": summary.grade_pyramid_sport,
                        "numeric_values": {
                            "highest_tried": self._convert_grade_to_numeric(
                                summary.highest_sport_grade_tried, "sport"
                            ),
                            "highest_clean": self._convert_grade_to_numeric(
                                summary.highest_grade_sport_sent_clean_on_lead, "sport"
                            ),
                            "onsight": self._convert_grade_to_numeric(
                                summary.onsight_grade_sport, "sport"
                            )
                        }
                    },
                    "trad": {
                        "highest_tried": summary.highest_trad_grade_tried,
                        "highest_clean_lead": summary.highest_grade_trad_sent_clean_on_lead,
                        "onsight": summary.onsight_grade_trad,
                        "pyramid": summary.grade_pyramid_trad,
                        "numeric_values": {
                            "highest_tried": self._convert_grade_to_numeric(
                                summary.highest_trad_grade_tried, "trad"
                            ),
                            "highest_clean": self._convert_grade_to_numeric(
                                summary.highest_grade_trad_sent_clean_on_lead, "trad"
                            ),
                            "onsight": self._convert_grade_to_numeric(
                                summary.onsight_grade_trad, "trad"
                            )
                        }
                    },
                    "boulder": {
                        "highest_tried": summary.highest_boulder_grade_tried,
                        "highest_clean": summary.highest_grade_boulder_sent_clean,
                        "flash": summary.flash_grade_boulder,
                        "pyramid": summary.grade_pyramid_boulder,
                        "numeric_values": {
                            "highest_tried": self._convert_grade_to_numeric(
                                summary.highest_boulder_grade_tried, "boulder"
                            ),
                            "highest_clean": self._convert_grade_to_numeric(
                                summary.highest_grade_boulder_sent_clean, "boulder"
                            ),
                            "flash": self._convert_grade_to_numeric(
                                summary.flash_grade_boulder, "boulder"
                            )
                        }
                    }
                },
                "style_preferences": {
                    "angles": {
                        "favorite": summary.favorite_angle.value if summary.favorite_angle else None,
                        "strongest": summary.strongest_angle.value if summary.strongest_angle else None,
                        "weakest": summary.weakest_angle.value if summary.weakest_angle else None
                    },
                    "energy_types": {
                        "favorite": summary.favorite_energy_type.value if summary.favorite_energy_type else None,
                        "strongest": summary.strongest_energy_type.value if summary.strongest_energy_type else None,
                        "weakest": summary.weakest_energy_type.value if summary.weakest_energy_type else None
                    },
                    "hold_types": {
                        "favorite": summary.favorite_hold_types.value if summary.favorite_hold_types else None,
                        "strongest": summary.strongest_hold_types.value if summary.strongest_hold_types else None,
                        "weakest": summary.weakest_hold_types.value if summary.weakest_hold_types else None
                    }
                }
            },
            "training_context": {
                "frequency": summary.training_frequency,
                "session_length": summary.typical_session_length.value if summary.typical_session_length else None,
                "facilities": {
                    "has_hangboard": summary.has_hangboard,
                    "has_home_wall": summary.has_home_wall,
                    "goes_to_gym": summary.goes_to_gym
                },
                "willing_to_train_indoors": summary.willing_to_train_indoors
            },
            "health_metrics": {
                "sleep_score": summary.sleep_score.value if summary.sleep_score else None,
                "nutrition_score": summary.nutrition_score.value if summary.nutrition_score else None,
                "injuries": {
                    "current": summary.current_injuries,
                    "history": summary.injury_history
                },
                "physical_limitations": summary.physical_limitations
            },
            "goals_and_projects": {
                "stated_goals": summary.climbing_goals,
                "current_projects": summary.current_projects,
                "recent_favorites": summary.recent_favorite_routes
            },
            "additional_context": {
                "preferred_crag": summary.preferred_crag_last_year,
                "notes": summary.additional_notes
            }
        }

    def _calculate_experience_level(self, summary: Any) -> str:
        """Determines climber experience level based on metrics"""
        # Get highest grade across disciplines
        sport_grade = self._convert_grade_to_numeric(summary.highest_grade_sport_sent_clean_on_lead, "sport")
        trad_grade = self._convert_grade_to_numeric(summary.highest_grade_trad_sent_clean_on_lead, "trad")
        boulder_grade = self._convert_grade_to_numeric(summary.highest_grade_boulder_sent_clean, "boulder")
        
        # Use years of experience as a factor
        years_exp = summary.years_climbing_outside or 0
        total_climbs = summary.total_climbs or 0
        
        # Advanced criteria: High grades OR moderate grades with significant experience
        if (sport_grade >= 17 or trad_grade >= 17 or boulder_grade >= 108) and total_climbs > 500:  # 5.12a/V8
            return "advanced"
        elif (sport_grade >= 14 or trad_grade >= 14 or boulder_grade >= 105) and (total_climbs > 200 or years_exp >= 3):  # 5.11a/V5
            return "intermediate"
        elif total_climbs < 100:
            return "beginner"
        else:
            return "unknown"


    def _convert_grade_to_numeric(self, grade: Optional[str], discipline: str) -> int:
        """Converts climbing grades to numeric values using GradeProcessor"""
        if not grade:
            return 0
        codes = self.grade_processor.convert_grades_to_codes([grade], discipline)
        return codes[0] if codes else 0