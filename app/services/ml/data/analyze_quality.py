from sqlalchemy import create_engine, text
import pandas as pd
import os
from dotenv import load_dotenv

def analyze_quality():
    # Load environment variables
    load_dotenv()
    
    # Use PRODUCTION database URL
    db_url = os.getenv('PRODUCTION_DATABASE_URL')
    engine = create_engine(db_url)
    
    # Get user quality analysis
    sql = """
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
            EXTRACT(days FROM (MAX(tick_date)::timestamp - MIN(tick_date)::timestamp)) as climbing_span_days,
            COUNT(*) FILTER (WHERE created_at > '2024-01-01') as recent_activity
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
            climbing_span_days >= 365
        THEN TRUE ELSE FALSE END as is_quality_user
    FROM user_metrics
    ORDER BY good_notes_ratio DESC, completion_ratio DESC;
    """
    
    df = pd.read_sql(text(sql), engine)
    
    print("\n=== Overall Statistics ===")
    print(f"Total Users: {len(df)}")
    print(f"Quality Users: {df['is_quality_user'].sum()}")
    
    print("\nDetailed User Analysis (Top 10 by Note Quality):")
    print(df[['username', 'total_ticks', 'avg_note_length', 'good_notes_ratio', 
              'discipline_count', 'unique_grades', 'completion_ratio', 'climbing_span_days']].head(10))
    
    print("\nMetric Distributions:")
    print("\nNote Length Distribution:")
    print(pd.cut(df['avg_note_length'], bins=[0, 20, 50, 100, 200]).value_counts())
    
    print("\nDiscipline Count Distribution:")
    print(df['discipline_count'].value_counts())
    
    print("\nClimbing Span Distribution (years):")
    print(pd.cut(df['climbing_span_days']/365, bins=[0, 1, 2, 5, 10, 20]).value_counts())

if __name__ == "__main__":
    analyze_quality() 