import pandas as pd
from app.services.climb_classifier import ClimbClassifier
from sqlalchemy import create_engine, text
import os
from datetime import datetime

# Database connection parameters
DATABASE_URL = "postgresql://localhost/climbing_analytics"
engine = create_engine(DATABASE_URL)

def test_new_classifier(csv_path: str, username: str):
    """Test the new classifier against CSV data"""
    
    # Read input CSV
    input_df = pd.read_csv(csv_path)
    
    # Rename columns to match expected names
    input_df = input_df.rename(columns={
        'Date': 'tick_date',
        'Route': 'route_name',
        'Route Type': 'route_type',
        'Lead Style': 'lead_style',
        'Rating': 'route_grade',
        'Length': 'length',
        'Style': 'style',
        'Rating Code': 'binned_code',
        'Notes': 'notes'  # Add Notes column
    })
    
    # Initialize classifier
    classifier = ClimbClassifier()
    
    # Apply new classification
    input_df['new_discipline'] = classifier.classify_discipline(input_df)
    
    # Query current database classifications
    query = text("""
        SELECT 
            ut.*,
            CASE 
                WHEN sp.id IS NOT NULL THEN 'sport'
                WHEN tp.id IS NOT NULL THEN 'trad'
                WHEN bp.id IS NOT NULL THEN 'boulder'
                ELSE 'unclassified'
            END as db_discipline
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
    """)
    
    with engine.connect() as conn:
        db_df = pd.read_sql(query, conn, params={"username": username})
    
    # Analysis results
    analysis = {
        "total_routes": len(input_df),
        "original_type_distribution": input_df['route_type'].value_counts().to_dict(),
        "new_classification_distribution": input_df['new_discipline'].value_counts().to_dict(),
        "current_db_distribution": db_df['db_discipline'].value_counts().to_dict()
    }
    
    # Analyze mixed type classifications
    mixed_routes = input_df[input_df['route_type'].str.contains(',', na=False)]
    analysis["mixed_type_results"] = {
        "total_mixed": len(mixed_routes),
        "type_breakdown": mixed_routes['route_type'].value_counts().to_dict(),
        "new_classifications": mixed_routes['new_discipline'].value_counts().to_dict()
    }
    
    # Analyze classification changes by lead style
    lead_style_analysis = {}
    for style in input_df['lead_style'].unique():
        if pd.notna(style):
            style_df = input_df[input_df['lead_style'] == style]
            lead_style_analysis[style] = {
                "count": len(style_df),
                "classifications": style_df['new_discipline'].value_counts().to_dict()
            }
    analysis["lead_style_classifications"] = lead_style_analysis
    
    # Detailed analysis of Trad/Sport combinations
    trad_sport_routes = input_df[
        input_df['route_type'].str.contains('Trad.*Sport|Sport.*Trad', case=False, na=False)
    ]
    
    # Define gear-related keywords
    gear_keywords = [
        'gear', 'trad', 'placed', 'protection', 'cam', 'nut', 'hex', 'stopper',
        'rack', 'piece', 'pro', 'placement', 'traditional'
    ]
    sport_keywords = [
        'bolt', 'sport', 'quickdraw', 'draw', 'clip', 'anchor', 'chain', 'lower'
    ]
    
    def find_keywords(text, keywords):
        if pd.isna(text):
            return []
        text = text.lower()
        return [kw for kw in keywords if kw in text]
    
    trad_sport_analysis = {
        "total_routes": len(trad_sport_routes),
        "classifications": trad_sport_routes['new_discipline'].value_counts().to_dict(),
        "details": []
    }
    
    # Analyze each Trad/Sport route
    for _, route in trad_sport_routes.iterrows():
        # Find gear indicators in style and notes
        style_gear_indicators = find_keywords(route['style'], gear_keywords)
        notes_gear_indicators = find_keywords(route['notes'], gear_keywords)
        style_sport_indicators = find_keywords(route['style'], sport_keywords)
        notes_sport_indicators = find_keywords(route['notes'], sport_keywords)
        
        trad_sport_analysis["details"].append({
            "route_name": route['route_name'],
            "route_type": route['route_type'],
            "lead_style": route['lead_style'],
            "style": route['style'],
            "notes": route['notes'] if pd.notna(route['notes']) else '',
            "gear_indicators": {
                "style": style_gear_indicators,
                "notes": notes_gear_indicators
            },
            "sport_indicators": {
                "style": style_sport_indicators,
                "notes": notes_sport_indicators
            },
            "classified_as": route['new_discipline']
        })
    
    analysis["trad_sport_analysis"] = trad_sport_analysis
    
    return analysis

def print_analysis(results):
    """Print pipeline analysis results in a formatted way"""
    print("\nClassification Analysis")
    print("=" * 50)
    
    print(f"\nTotal Routes Analyzed: {results['total_routes']}")
    
    print("\nOriginal Route Type Distribution:")
    for type_, count in results['original_type_distribution'].items():
        print(f"  {type_}: {count}")
    
    print("\nNew Classification Distribution:")
    for discipline, count in results['new_classification_distribution'].items():
        if pd.notna(discipline):
            print(f"  {discipline}: {count}")
    
    print("\nCurrent Database Distribution:")
    for discipline, count in results['current_db_distribution'].items():
        print(f"  {discipline}: {count}")
    
    if "trad_sport_analysis" in results:
        print("\nTrad/Sport Routes Analysis:")
        ts_analysis = results["trad_sport_analysis"]
        print(f"Total Trad/Sport Routes: {ts_analysis['total_routes']}")
        
        print("\nClassifications:")
        for discipline, count in ts_analysis['classifications'].items():
            print(f"  {discipline}: {count}")
        
        print("\nDetailed Breakdown:")
        for route in ts_analysis['details']:
            print(f"\n  Route: {route['route_name']}")
            print(f"  Type: {route['route_type']}")
            print(f"  Lead Style: {route['lead_style']}")
            print(f"  Style: {route['style']}")
            print(f"  Notes: {route['notes']}")
            if route['gear_indicators']['style'] or route['gear_indicators']['notes']:
                print(f"  Gear Indicators:")
                if route['gear_indicators']['style']:
                    print(f"    Style: {', '.join(route['gear_indicators']['style'])}")
                if route['gear_indicators']['notes']:
                    print(f"    Notes: {', '.join(route['gear_indicators']['notes'])}")
            if route['sport_indicators']['style'] or route['sport_indicators']['notes']:
                print(f"  Sport Indicators:")
                if route['sport_indicators']['style']:
                    print(f"    Style: {', '.join(route['sport_indicators']['style'])}")
                if route['sport_indicators']['notes']:
                    print(f"    Notes: {', '.join(route['sport_indicators']['notes'])}")
            print(f"  Classified As: {route['classified_as']}")
    
    print("\nMixed Type Analysis:")
    mixed = results['mixed_type_results']
    print(f"Total Mixed Type Routes: {mixed['total_mixed']}")
    print("\nMixed Type Breakdown:")
    for type_, count in mixed['type_breakdown'].items():
        print(f"  {type_}: {count}")
    print("\nNew Classifications for Mixed Types:")
    for discipline, count in mixed['new_classifications'].items():
        if pd.notna(discipline):
            print(f"  {discipline}: {count}")
    
    print("\nClassifications by Lead Style:")
    for style, data in results['lead_style_classifications'].items():
        print(f"\n  {style} ({data['count']} routes):")
        for discipline, count in data['classifications'].items():
            if pd.notna(discipline):
                print(f"    {discipline}: {count}")
    
    print("\nDetailed Mixed Type Examples:")
    print("=" * 50)
    
    # Get all mixed type routes
    mixed_routes = []
    for route in results["trad_sport_analysis"]["details"]:
        mixed_routes.append({
            "name": route["route_name"],
            "type": route["route_type"],
            "style": route["style"],
            "lead_style": route["lead_style"],
            "notes": route["notes"],
            "classified_as": route["classified_as"]
        })
    
    # Split into classified and unclassified
    classified = [r for r in mixed_routes if r["classified_as"] is not None]
    unclassified = [r for r in mixed_routes if r["classified_as"] is None]
    
    print("\nCLASSIFIED EXAMPLES:")
    for route in classified[:5]:  # Show first 5 classified routes
        print(f"\n  Route: {route['name']}")
        print(f"  Type: {route['type']}")
        print(f"  Style: {route['style']}")
        print(f"  Lead Style: {route['lead_style']}")
        print(f"  Notes: {route['notes']}")
        print(f"  Classified As: {route['classified_as']}")
    
    print("\nUNCLASSIFIED EXAMPLES:")
    for route in unclassified[:5]:  # Show first 5 unclassified routes
        print(f"\n  Route: {route['name']}")
        print(f"  Type: {route['type']}")
        print(f"  Style: {route['style']}")
        print(f"  Lead Style: {route['lead_style']}")
        print(f"  Notes: {route['notes']}")
        print(f"  Classified As: {route['classified_as']}")
    
    print("\nALL UNCLASSIFIED MIXED ROUTES:")
    print("=" * 50)
    
    # Get all mixed routes (any route type containing a comma)
    mixed_routes = []
    for route in results["trad_sport_analysis"]["details"]:
        if route["classified_as"] is None:
            print(f"\nRoute: {route['route_name']}")
            print(f"Type: {route['route_type']}")
            print(f"Style: {route['style']}")
            print(f"Lead Style: {route['lead_style']}")
            print(f"Notes: {route['notes']}")
            if route['gear_indicators']['style'] or route['gear_indicators']['notes']:
                print(f"Gear Indicators:")
                if route['gear_indicators']['style']:
                    print(f"  Style: {', '.join(route['gear_indicators']['style'])}")
                if route['gear_indicators']['notes']:
                    print(f"  Notes: {', '.join(route['gear_indicators']['notes'])}")
            if route['sport_indicators']['style'] or route['sport_indicators']['notes']:
                print(f"Sport Indicators:")
                if route['sport_indicators']['style']:
                    print(f"  Style: {', '.join(route['sport_indicators']['style'])}")
                if route['sport_indicators']['notes']:
                    print(f"  Notes: {', '.join(route['sport_indicators']['notes'])}")
            print("-" * 30)

def analyze_database_quality(engine, username: str):
    """Analyze database quality issues"""
    
    queries = {
        "missing_grades": """
            SELECT route_name, route_grade, discipline, tick_date
            FROM user_ticks 
            WHERE username = :username 
            AND (route_grade IS NULL OR route_grade = '')
        """,
        
        "missing_lengths": """
            SELECT route_name, length_category, discipline, tick_date
            FROM user_ticks 
            WHERE username = :username 
            AND (length_category IS NULL OR length_category = '')
        """,
        
        "missing_binned_codes": """
            SELECT route_name, binned_code, route_grade, tick_date
            FROM user_ticks 
            WHERE username = :username 
            AND binned_code IS NULL
        """,
        
        "pyramid_mismatches": """
            SELECT ut.route_name, ut.tick_date, ut.discipline,
                CASE 
                    WHEN sp.id IS NOT NULL THEN 'sport'
                    WHEN tp.id IS NOT NULL THEN 'trad'
                    WHEN bp.id IS NOT NULL THEN 'boulder'
                    ELSE 'missing'
                END as pyramid_type
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
            AND (
                (ut.discipline = 'sport' AND sp.id IS NULL) OR
                (ut.discipline = 'trad' AND tp.id IS NULL) OR
                (ut.discipline = 'boulder' AND bp.id IS NULL)
            )
        """,
        
        "duplicate_entries": """
            SELECT route_name, tick_date, COUNT(*) as count
            FROM user_ticks
            WHERE username = :username
            GROUP BY route_name, tick_date
            HAVING COUNT(*) > 1
        """,
        
        "inconsistent_grades": """
            SELECT DISTINCT a.route_name, a.route_grade as grade1, b.route_grade as grade2
            FROM user_ticks a
            JOIN user_ticks b ON a.route_name = b.route_name
                AND a.username = b.username
                AND a.route_grade != b.route_grade
            WHERE a.username = :username
        """,
        
        "discipline_stats": """
            SELECT 
                discipline,
                COUNT(*) as total_routes,
                COUNT(CASE WHEN send_bool = true THEN 1 END) as sends,
                COUNT(CASE WHEN send_bool = false THEN 1 END) as attempts
            FROM user_ticks
            WHERE username = :username
            GROUP BY discipline
        """,
        
        "missing_disciplines": """
            SELECT route_name, tick_date, lead_style, discipline
            FROM user_ticks
            WHERE username = :username
            AND (discipline IS NULL OR discipline = '')
        """,
        
        "length_category_distribution": """
            SELECT 
                discipline,
                length_category,
                COUNT(*) as count,
                array_agg(DISTINCT route_name) as sample_routes
            FROM user_ticks
            WHERE username = :username
            GROUP BY discipline, length_category
            ORDER BY discipline, length_category
        """,
        
        "missing_lengths_by_type": """
            SELECT 
                discipline,
                COUNT(*) as missing_count,
                array_agg(route_name) as routes
            FROM user_ticks 
            WHERE username = :username 
            AND (length_category IS NULL OR length_category = '')
            GROUP BY discipline
            ORDER BY missing_count DESC
        """
    }
    
    results = {}
    with engine.connect() as conn:
        for name, query in queries.items():
            df = pd.read_sql(text(query), conn, params={"username": username})
            results[name] = df
            
    return results

def print_database_analysis(results):
    """Print database quality analysis results"""
    print("\nDatabase Quality Analysis")
    print("=" * 50)
    
    for issue, df in results.items():
        print(f"\n{issue.replace('_', ' ').title()}:")
        if len(df) > 0:
            print(f"Found {len(df)} issues:")
            print(df.to_string())
        else:
            print("No issues found")
            
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python3 test_classifier.py <csv_file> <username>")
        sys.exit(1)
        
    csv_file = sys.argv[1]
    username = sys.argv[2]
    
    # Run original analysis
    results = test_new_classifier(csv_file, username)
    print_analysis(results)
    
    # Run database quality analysis
    print("\n" + "=" * 80 + "\n")
    print("ANALYZING DATABASE QUALITY")
    print("=" * 80)
    db_results = analyze_database_quality(engine, username)
    print_database_analysis(db_results) 