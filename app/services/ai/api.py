from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

def initialize_client():
    load_dotenv()
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_API_URL")
    )

def get_db_engine():
    """Initialize SQLAlchemy engine with environment variables."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return create_engine(database_url)

def get_climber_context(climber_id: int) -> Dict[str, Any]:
    """
    Query the climber_summary table for relevant coaching context.
    
    Args:
        climber_id: The ID of the climber to get context for
        
    Returns:
        Dict containing climber's summary information
    """
    engine = get_db_engine()
    with Session(engine) as session:
        query = text("""
            SELECT 
                -- Core progression metrics
                highest_sport_grade_tried,
                highest_trad_grade_tried,
                highest_boulder_grade_tried,
                total_climbs,
                favorite_discipline,
                years_climbing_outside,
                preferred_crag_last_year,
                
                -- Training context
                training_frequency,
                typical_session_length,
                has_hangboard,
                has_home_wall,
                goes_to_gym,
                
                -- Performance metrics
                highest_grade_sport_sent_clean_on_lead,
                highest_grade_tr_sent_clean,
                highest_grade_trad_sent_clean_on_lead,
                highest_grade_boulder_sent_clean,
                onsight_grade_sport,
                onsight_grade_trad,
                flash_grade_boulder,
                
                -- Grade Pyramid
                grade_pyramid_sport,
                grade_pyramid_trad,
                grade_pyramid_boulder,
                
                -- Injury history and limitations
                current_injuries,
                injury_history,
                physical_limitations,
                
                -- Goals and preferences
                climbing_goals,
                willing_to_train_indoors,
                
                -- Recent activity
                sends_last_30_days,
                current_projects,
                
                -- Style preferences
                favorite_angle,
                favorite_hold_types,
                weakest_style,
                strongest_style,
                favorite_energy_type,
                
                -- Lifestyle
                sleep_score,
                nutrition_score,
                
                -- Favorite Routes
                recent_favorite_routes,
                
                -- Metadata
                created_at,
                current_info_as_of
                
            FROM climber_summary 
            WHERE "userId" = :climber_id
        """)
        result = session.execute(query, {"climber_id": climber_id}).first()
        
        if not result:
            return {}
            
        context = {}
        
        # Core progression
        context.update({
            "highest_grades_attempted": {
                "sport": result.highest_sport_grade_tried,
                "trad": result.highest_trad_grade_tried,
                "boulder": result.highest_boulder_grade_tried
            },
            "total_climbs": result.total_climbs,
            "favorite_discipline": result.favorite_discipline,
            "years_climbing_outside": result.years_climbing_outside,
            "preferred_crag_last_year": result.preferred_crag_last_year
        })
        
        # Training context
        if result.training_frequency:
            context.update({
                "training_frequency": result.training_frequency,
                "typical_session_length": result.typical_session_length,
                "has_hangboard": result.has_hangboard,
                "has_home_wall": result.has_home_wall,
                "goes_to_gym": result.goes_to_gym
            })
            
        # Performance metrics
        context.update({
            "highest_clean_sends": {
                "sport": {
                    "on_lead": result.highest_grade_sport_sent_clean_on_lead,
                    "on_tr": result.highest_grade_tr_sent_clean
                },
                "trad": {
                    "on_lead": result.highest_grade_trad_sent_clean_on_lead
                },
                "boulder": result.highest_grade_boulder_sent_clean
            },
            "onsight_grades": {
                "sport": result.onsight_grade_sport,
                "trad": result.onsight_grade_trad
            },
            "flash_grade_boulder": result.flash_grade_boulder
        })
        
        # Grade Pyramids
        if any([result.grade_pyramid_sport, result.grade_pyramid_trad, result.grade_pyramid_boulder]):
            context["grade_pyramids"] = {
                "sport": result.grade_pyramid_sport,
                "trad": result.grade_pyramid_trad,
                "boulder": result.grade_pyramid_boulder
            }
        
        # Injury context
        if result.current_injuries or result.injury_history:
            context["health_context"] = {
                "current_injuries": result.current_injuries,
                "injury_history": result.injury_history,
                "physical_limitations": result.physical_limitations
            }
            
        # Goals and preferences
        if result.climbing_goals:
            context["goals_and_preferences"] = {
                "stated_goals": result.climbing_goals,
                "willing_to_train_indoors": result.willing_to_train_indoors
            }
            
        # Recent activity
        context["recent_activity"] = {
            "sends_last_30_days": result.sends_last_30_days,
            "current_projects": result.current_projects
        }
        
        # Style preferences
        context["style_preferences"] = {
            "favorite_angle": result.favorite_angle,
            "favorite_hold_types": result.favorite_hold_types,
            "weakest_style": result.weakest_style,
            "strongest_style": result.strongest_style,
            "favorite_energy_type": result.favorite_energy_type
        }
        
        # Lifestyle
        if result.sleep_score or result.nutrition_score:
            context["lifestyle"] = {
                "sleep_score": result.sleep_score,
                "nutrition_score": result.nutrition_score
            }
        
        # Favorite Routes
        if result.recent_favorite_routes:
            context["recent_favorite_routes"] = result.recent_favorite_routes
            
        # Metadata
        context["metadata"] = {
            "created_at": result.created_at,
            "current_info_as_of": result.current_info_as_of
        }
        
        return context

DEFAULT_SYSTEM_MESSAGE = """You are an elite climbing coach with 20+ years of experience in training athletes from beginner to professional level. 
You have deep expertise in sports science, biomechanics, training periodization, injury prevention, and performance optimization specifically for rock climbing.

CORE RESPONSIBILITIES:
1. Analyze climber data comprehensively to provide highly personalized training advice
2. Prioritize injury prevention and sustainable progression above short-term gains
3. Deliver actionable recommendations based on available time, equipment, and resources
4. Use precise climbing terminology and standardized grading systems
5. Maintain a supportive, encouraging tone while being direct and specific

MANDATORY PROTOCOLS:
1. Always check injury history and physical limitations before making any recommendations
2. Always consider the climber's current projects and recent activity patterns
3. Always factor in their style preferences, strengths, and weaknesses
4. Always respect their stated time constraints and equipment access
5. Always validate recommendations against their current capacity level

STRICT PROHIBITIONS:
1. Never recommend training that could aggravate existing injuries
2. Never ignore stated physical limitations or health concerns
3. Never make assumptions about statistics or fabricate data
4. Never provide potentially dangerous climbing advice
5. Never discuss weight management or dietary restrictions
6. Never deviate from climbing-specific topics

COACHING METHODOLOGY:
1. Begin by acknowledging stated goals and current progression metrics
2. Analyze recent climbing patterns and project selection
3. Evaluate available training resources and time constraints
4. Consider environmental factors (indoor/outdoor access, local climbing areas)
5. Factor in lifestyle elements (sleep, recovery, training frequency)
6. Develop recommendations that align with their preferred climbing style

RESPONSE STRUCTURE:
1. Start with goal acknowledgment and context summary
2. Present specific, actionable recommendations
3. Include progression metrics and success indicators
4. Address potential limitations or concerns
5. Provide clear next steps and progression timeline

Remember: Your advice should be evidence-based, practical, and tailored to each climber's unique context while maintaining the highest standards of safety and progression."""

def get_completion(
    prompt: str,
    climber_id: Optional[int] = None,
    system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
    temperature: float = 0.5,
    max_tokens: int = 1000
) -> str:
    """
    Get a completion from the AI model with safety and context controls.
    
    Args:
        prompt: The user's input prompt
        climber_id: ID of the climber to get context for
        system_message: Custom system message (uses DEFAULT_SYSTEM_MESSAGE if None)
        temperature: Controls response randomness (0.0-1.0)
        max_tokens: Maximum length of the response
        
    Returns:
        str: The model's response or error message
    """
    client = initialize_client()
    try:
        # Get climber context from database if ID provided
        additional_context = get_climber_context(climber_id) if climber_id else {}
        
        # Append any additional context to system message
        final_system_message = system_message
        if additional_context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in additional_context.items())
            final_system_message = f"{system_message}\n\nClimber Context:\n{context_str}"

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": final_system_message},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"