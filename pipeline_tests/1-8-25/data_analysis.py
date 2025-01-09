import pandas as pd
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timedelta
import numpy as np
import re

# Database connection parameters
DB_USER = "climb_user"
DB_PASSWORD = "zTPX2N8frS1mmC6z4hRFse7Vz9ADRODF"
DB_HOST = "dpg-cto9aajqf0us73amrqfg-a.oregon-postgres.render.com"
DB_NAME = "climbdb"

# Create database connection
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def analyze_pipeline(username: str, input_csv_path: str):
    """Analyze the full data processing pipeline from input CSV to database output"""
    
    # Read input CSV
    input_df = pd.read_csv(input_csv_path)
    
    # Rename columns to match database naming
    input_df = input_df.rename(columns={
        'Date': 'tick_date',
        'Route': 'route_name',
        'Route Type': 'type',
        'Lead Style': 'lead_style',
        'Rating': 'route_grade',
        'Length': 'length',
        'Style': 'style'  # Add Style column
    })
    
    # Query database
    user_ticks_query = text("""
        SELECT 
            ut.*,
            CASE 
                WHEN sp.id IS NOT NULL THEN 'sport'
                WHEN tp.id IS NOT NULL THEN 'trad'
                WHEN bp.id IS NOT NULL THEN 'boulder'
                ELSE 'unclassified'
            END as processed_discipline
        FROM user_ticks ut
        LEFT JOIN sport_pyramid sp 
            ON ut.route_name = sp.route_name 
            AND ut.tick_date = sp.tick_date 
            AND ut.username = sp.username
        LEFT JOIN trad_pyramid tp 
            ON ut.route_name = tp.route_name 
            AND ut.tick_date = tp.tick_date 
            AND ut.username = tp.username
        LEFT JOIN boulder_pyramid bp 
            ON ut.route_name = bp.route_name 
            AND ut.tick_date = bp.tick_date 
            AND ut.username = bp.username
        WHERE ut.username = :username
        ORDER BY ut.tick_date DESC
    """)
    
    with engine.connect() as conn:
        db_df = pd.read_sql(user_ticks_query, conn, params={"username": username})
    
    # Enhanced discipline mapping with style-based decisions
    def determine_discipline(row):
        route_type = row['type']
        style = row['style']
        lead_style = row['lead_style']
        
        # Handle simple cases first
        if route_type in ['Sport', 'Trad', 'Boulder']:
            return route_type.lower()
            
        # Handle mixed types
        if pd.isna(route_type):
            return None
            
        types = [t.strip() for t in route_type.split(',')]
        
        # Sport/TR combinations
        if ('Sport' in types and 'TR' in types) or route_type in ['Sport, TR', 'TR, Sport']:
            if pd.notna(lead_style) and any(ls in str(lead_style) for ls in ['Lead', 'Onsight', 'Flash', 'Redpoint', 'Pinkpoint']):
                return 'sport'
            if pd.notna(style) and 'Lead' in str(style):
                return 'sport'
            return 'sport'  # Default to sport if unclear
            
        # Trad/TR combinations
        if ('Trad' in types and 'TR' in types) or route_type in ['Trad, TR', 'TR, Trad']:
            if pd.notna(lead_style) and any(ls in str(lead_style) for ls in ['Lead', 'Onsight', 'Flash', 'Redpoint', 'Pinkpoint']):
                return 'trad'
            if pd.notna(style) and 'Lead' in str(style):
                return 'trad'
            return 'trad'  # Default to trad if unclear
            
        # Trad/Sport combinations
        if ('Trad' in types and 'Sport' in types) or route_type in ['Trad, Sport', 'Sport, Trad']:
            # If there's any indication of gear placement, prefer trad
            if pd.notna(style) and any(s in str(style) for s in ['Gear', 'Trad']):
                return 'trad'
            return 'sport'  # Default to sport if unclear
            
        # Handle Alpine/Trad
        if 'Alpine' in types and 'Trad' in types:
            return 'trad'
            
        # Default cases based on primary type
        if 'Sport' in types:
            return 'sport'
        if 'Trad' in types:
            return 'trad'
        if 'Boulder' in types:
            return 'boulder'
            
        return None
    
    # Apply enhanced discipline mapping
    input_df['mapped_discipline'] = input_df.apply(determine_discipline, axis=1)
    
    # Analyze style distributions for mixed types
    mixed_routes = input_df[input_df['type'].str.contains(',', na=False)]
    style_analysis = {
        'mixed_types': mixed_routes['type'].value_counts().to_dict(),
        'style_by_type': {
            route_type: mixed_routes[mixed_routes['type'] == route_type]['style'].value_counts().to_dict()
            for route_type in mixed_routes['type'].unique()
        },
        'lead_style_by_type': {
            route_type: mixed_routes[mixed_routes['type'] == route_type]['lead_style'].value_counts().to_dict()
            for route_type in mixed_routes['type'].unique()
        },
        'mapped_disciplines': mixed_routes['mapped_discipline'].value_counts().to_dict()
    }
    
    # Pipeline Analysis
    analysis = {
        "input_stats": {
            "total_records": len(input_df),
            "unique_routes": len(input_df['route_name'].unique()),
            "input_disciplines": input_df['type'].value_counts().to_dict(),
            "mapped_disciplines": input_df['mapped_discipline'].value_counts().to_dict(),
            "style_analysis": style_analysis
        },
        "output_stats": {
            "total_records": len(db_df),
            "unique_routes": len(db_df['route_name'].unique()),
            "output_disciplines": db_df['discipline'].value_counts().to_dict(),
            "processed_disciplines": db_df['processed_discipline'].value_counts().to_dict()
        }
    }
    
    # Merge input and output data
    merged_df = pd.merge(
        input_df, 
        db_df[['route_name', 'tick_date', 'discipline', 'processed_discipline']], 
        on=['route_name', 'tick_date'], 
        how='outer',
        suffixes=('_input', '')
    )
    
    # Find mismatches between mapped discipline and final classification
    mismatches = merged_df[
        (merged_df['mapped_discipline'] != merged_df['processed_discipline']) &
        (merged_df['processed_discipline'].notna())
    ]
    
    if not mismatches.empty:
        analysis["discipline_mismatches"] = {
            "total_mismatches": len(mismatches),
            "mismatch_patterns": mismatches.groupby(
                ['type', 'mapped_discipline', 'processed_discipline']
            ).size().reset_index(name='count').to_dict('records'),
            "sample_mismatches": mismatches[[
                'route_name', 'type', 'mapped_discipline', 'processed_discipline'
            ]].head(10).to_dict('records')
        }
    
    # Analyze missing entries
    missing_in_db = merged_df[merged_df['discipline'].isna()]
    if not missing_in_db.empty:
        analysis["missing_entries"] = {
            "total_missing": len(missing_in_db),
            "missing_by_type": missing_in_db['type'].value_counts().to_dict(),
            "sample_missing": missing_in_db[[
                'route_name', 'type', 'tick_date', 'mapped_discipline'
            ]].head(10).to_dict('records')
        }
    
    return analysis

def print_pipeline_analysis(results):
    """Print pipeline analysis results in a formatted way"""
    print("\nData Pipeline Analysis")
    print("=" * 50)
    
    print("\nInput Statistics:")
    print(f"Total records: {results['input_stats']['total_records']}")
    print(f"Unique routes: {results['input_stats']['unique_routes']}")
    
    print("\nOriginal Input Disciplines:")
    for discipline, count in results['input_stats']['input_disciplines'].items():
        print(f"  {discipline}: {count}")
    
    print("\nMapped Disciplines (after processing mixed types):")
    for discipline, count in results['input_stats']['mapped_disciplines'].items():
        if pd.notna(discipline):  # Only show valid disciplines
            print(f"  {discipline}: {count}")
    
    print("\nMixed Type Analysis:")
    style_analysis = results['input_stats']['style_analysis']
    
    print("\n  Mixed Routes Mapped To:")
    for discipline, count in style_analysis['mapped_disciplines'].items():
        if pd.notna(discipline):
            print(f"    {discipline}: {count}")
    
    print("\n  Mixed Type Details:")
    for type_, count in style_analysis['mixed_types'].items():
        print(f"\n  {type_}: {count}")
        print("    Lead Styles:")
        for lead_style, lead_count in style_analysis['lead_style_by_type'][type_].items():
            print(f"      {lead_style}: {lead_count}")
    
    print("\nDatabase Output Statistics:")
    print(f"Total records: {results['output_stats']['total_records']}")
    print(f"Unique routes: {results['output_stats']['unique_routes']}")
    print("\nProcessed Disciplines in Database:")
    for discipline, count in results['output_stats']['processed_disciplines'].items():
        print(f"  {discipline}: {count}")
    
    if "discipline_mismatches" in results:
        print("\nDiscipline Classification Issues:")
        print(f"Total mismatches: {results['discipline_mismatches']['total_mismatches']}")
        
        print("\nMismatch Patterns:")
        for pattern in results['discipline_mismatches']['mismatch_patterns']:
            print(f"  {pattern['type']} -> Expected: {pattern['mapped_discipline']}, "
                  f"Got: {pattern['processed_discipline']}: {pattern['count']}")
        
        print("\nSample Mismatches:")
        for mismatch in results['discipline_mismatches']['sample_mismatches']:
            print(f"  {mismatch['route_name']}: {mismatch['type']} -> "
                  f"Expected: {mismatch['mapped_discipline']}, "
                  f"Got: {mismatch['processed_discipline']}")
    
    if "missing_entries" in results:
        print("\nMissing Database Entries:")
        print(f"Total missing: {results['missing_entries']['total_missing']}")
        print("\nMissing by Type:")
        for type_, count in results['missing_entries']['missing_by_type'].items():
            print(f"  {type_}: {count}")
        
        print("\nSample Missing Entries:")
        for entry in results['missing_entries']['sample_missing']:
            print(f"  {entry['route_name']} ({entry['type']}) - {entry['tick_date']}")
            if pd.notna(entry['mapped_discipline']):
                print(f"    Would have been mapped to: {entry['mapped_discipline']}")

if __name__ == "__main__":
    username = "isaac-rubey"
    input_csv = "./ticks-3.csv"  # Updated path
    results = analyze_pipeline(username, input_csv)
    print_pipeline_analysis(results) 