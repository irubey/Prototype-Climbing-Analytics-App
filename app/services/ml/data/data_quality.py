from sqlalchemy import text
import pandas as pd
import numpy as np
from app import db
import torch
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import logging

logger = logging.getLogger(__name__)

def analyze_data_quality():
    """Analyze data quality and distribution across all prediction targets"""
    query = text("""
        WITH grade_analysis AS (
            SELECT 
                -- Analyze binned_code structure
                LEFT(binned_code::text, 1) as discipline_code,
                RIGHT(binned_code::text, 2) as difficulty_value,
                discipline,
                COUNT(*) as count
            FROM user_ticks
            WHERE binned_code IS NOT NULL
            GROUP BY discipline_code, difficulty_value, discipline
        ),
        enum_validation AS (
            SELECT
                -- Validate enum fields
                discipline,
                lead_style,
                length_category,
                difficulty_category,
                COUNT(*) as count,
                -- Check for invalid values
                CASE WHEN discipline NOT IN ('sport', 'trad', 'boulder', 'tr') 
                     THEN TRUE ELSE FALSE END as invalid_discipline,
                CASE WHEN lead_style NOT IN ('Redpoint', 'Flash', 'Onsight', 'Pinkpoint') 
                     THEN TRUE ELSE FALSE END as invalid_lead_style,
                CASE WHEN length_category NOT IN ('short', 'medium', 'long', 'multipitch') 
                     THEN TRUE ELSE FALSE END as invalid_length,
                CASE WHEN difficulty_category NOT IN ('Project', 'Tier 2', 'Tier 3', 'Base Volume') 
                     THEN TRUE ELSE FALSE END as invalid_difficulty
            FROM user_ticks
            GROUP BY discipline, lead_style, length_category, difficulty_category
        ),
        send_analysis AS (
            SELECT
                discipline,
                difficulty_category,
                send_bool,
                COUNT(*) as count,
                COUNT(*) filter (WHERE notes IS NOT NULL AND LENGTH(notes) >= 20) as count_with_good_notes
            FROM user_ticks 
            GROUP BY discipline, difficulty_category, send_bool
        )
        SELECT 
            -- Grade distribution
            ga.discipline,
            ga.discipline_code,
            ga.difficulty_value::int as grade_difficulty,
            ga.count as grade_count,
            
            -- Enum validation
            ev.lead_style,
            ev.length_category,
            ev.difficulty_category,
            ev.count as enum_count,
            ev.invalid_discipline,
            ev.invalid_lead_style,
            ev.invalid_length,
            ev.invalid_difficulty,
            
            -- Send analysis
            sa.send_bool,
            sa.count as send_count,
            sa.count_with_good_notes,
            
            -- Calculate quality metrics
            CASE 
                WHEN sa.count_with_good_notes::float / NULLIF(sa.count, 0) >= 0.8 
                AND NOT (ev.invalid_discipline OR ev.invalid_lead_style OR 
                        ev.invalid_length OR ev.invalid_difficulty)
                THEN TRUE 
                ELSE FALSE 
            END as is_quality_data
            
        FROM grade_analysis ga
        FULL OUTER JOIN enum_validation ev 
            ON ga.discipline = ev.discipline
        FULL OUTER JOIN send_analysis sa 
            ON ga.discipline = sa.discipline 
            AND ev.difficulty_category = sa.difficulty_category
        ORDER BY ga.discipline, ga.difficulty_value::int
    """)
    
    return pd.read_sql(query, db.engine)

def validate_binned_codes():
    """Specifically validate binned_code structure and relationships"""
    query = text("""
        SELECT 
            binned_code,
            LEFT(binned_code::text, 1) as discipline_code,
            RIGHT(binned_code::text, 2) as difficulty_value,
            discipline,
            COUNT(*) as count,
            -- Validate discipline code matches discipline
            CASE 
                WHEN discipline = 'sport' AND LEFT(binned_code::text, 1) = '1' THEN TRUE
                WHEN discipline = 'trad' AND LEFT(binned_code::text, 1) = '2' THEN TRUE
                WHEN discipline = 'boulder' AND LEFT(binned_code::text, 1) = '3' THEN TRUE
                WHEN discipline = 'tr' AND LEFT(binned_code::text, 1) = '4' THEN TRUE
                ELSE FALSE
            END as valid_discipline_code,
            -- Check difficulty value range
            RIGHT(binned_code::text, 2)::int as numeric_difficulty
        FROM user_ticks
        WHERE binned_code IS NOT NULL
        GROUP BY binned_code, discipline
        ORDER BY discipline, binned_code
    """)
    
    return pd.read_sql(query, db.engine)

def get_quality_training_data():
    """Get high-quality training data ensuring all fields are valid and have sufficient examples"""
    query = text("""
        WITH valid_data AS (
            SELECT *
            FROM user_ticks
            WHERE notes IS NOT NULL
                AND LENGTH(notes) >= 20
                AND binned_code IS NOT NULL
                AND discipline IN ('sport', 'trad', 'boulder')
                AND lead_style IN ('Redpoint', 'Flash', 'Onsight', 'Pinkpoint')
                AND length_category IN ('short', 'medium', 'long', 'multipitch')
        ),
        sampled_data AS (
            SELECT *,
                ROW_NUMBER() OVER (ORDER BY RANDOM()) as rn
            FROM valid_data
        )
        SELECT 
            notes,
            discipline,
            lead_style,
            length_category,
            difficulty_category,
            binned_code
        FROM sampled_data
        WHERE rn <= 1000  -- Take up to 1000 examples
        ORDER BY RANDOM()
    """)
    
    logger.info("Fetching quality training data from database...")
    df = pd.read_sql(query, db.engine)
    
    # Validate we have enough examples
    if len(df) < 100:  # Minimum dataset size
        raise ValueError(f"Insufficient training data: only {len(df)} examples found")
    
    # Log distributions
    logger.info(f"Final dataset size: {len(df)} examples")
    logger.info(f"Discipline distribution: {df['discipline'].value_counts(normalize=True).to_dict()}")
    logger.info(f"Lead style distribution: {df['lead_style'].value_counts(normalize=True).to_dict()}")
    logger.info(f"Length distribution: {df['length_category'].value_counts(normalize=True).to_dict()}")
    
    return df

def analyze_grade_distribution():
    """Analyze the distribution of grades in the training data"""
    query = text("""
        SELECT 
            binned_code,
            discipline,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE notes IS NOT NULL AND LENGTH(notes) >= 20) as count_with_notes
        FROM user_ticks
        WHERE binned_code IS NOT NULL
        GROUP BY binned_code, discipline
        ORDER BY binned_code
    """)
    
    return pd.read_sql(query, db.engine)

def identify_quality_users():
    """Identify users providing consistently high-quality data"""
    query = text("""
        WITH user_metrics AS (
            SELECT 
                username,
                COUNT(*) as total_ticks,
                AVG(LENGTH(notes)) as avg_note_length,
                COUNT(*) FILTER (WHERE LENGTH(notes) >= 20) / COUNT(*)::float as good_notes_ratio,
                COUNT(*) FILTER (WHERE discipline IS NOT NULL AND lead_style IS NOT NULL AND length_category IS NOT NULL AND difficulty_category IS NOT NULL)::float / COUNT(*) as completion_ratio,
                COUNT(DISTINCT binned_code) as unique_grades,
                COUNT(DISTINCT discipline) as discipline_count,
                COUNT(DISTINCT lead_style) as style_count,
                MAX(tick_date)::date - MIN(tick_date)::date as climbing_span,
                COUNT(*) FILTER (WHERE created_at > '2024-01-01') as recent_activity,
                COUNT(*)::float / NULLIF(DATE_PART('day', MAX(tick_date)::date - MIN(tick_date)::date), 0) as climbing_density
            FROM user_ticks
            GROUP BY username
            HAVING COUNT(*) >= 20
        )
        SELECT *,
            CASE WHEN 
                avg_note_length >= 20 AND 
                good_notes_ratio >= 0.3 AND 
                completion_ratio >= 0.4 AND 
                unique_grades >= 3 AND 
                discipline_count >= 2 AND
                climbing_span >= 365
            THEN TRUE ELSE FALSE END as is_quality_user
        FROM user_metrics
        ORDER BY is_quality_user DESC, good_notes_ratio DESC, completion_ratio DESC
    """)
    
    return pd.read_sql(query, db.engine)
