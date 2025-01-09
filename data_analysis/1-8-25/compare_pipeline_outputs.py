import pandas as pd
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connections
local_db_url = "postgresql://localhost/climbing_analytics"
remote_db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

def get_db_data(connection_url, username="isaac-rubey"):
    """Get all relevant data for a user from a database"""
    engine = create_engine(connection_url)
    
    # Get data from all relevant tables
    with engine.connect() as conn:
        user_ticks = pd.read_sql(f"SELECT * FROM user_ticks WHERE username = '{username}'", conn)
        sport_pyramid = pd.read_sql(f"SELECT * FROM sport_pyramid WHERE username = '{username}'", conn)
        trad_pyramid = pd.read_sql(f"SELECT * FROM trad_pyramid WHERE username = '{username}'", conn)
        boulder_pyramid = pd.read_sql(f"SELECT * FROM boulder_pyramid WHERE username = '{username}'", conn)
    
    return {
        'user_ticks': user_ticks,
        'sport_pyramid': sport_pyramid,
        'trad_pyramid': trad_pyramid,
        'boulder_pyramid': boulder_pyramid
    }

def analyze_data_coverage(old_data, new_data):
    """Analyze data coverage and completeness"""
    results = []
    
    for table_name in ['user_ticks', 'sport_pyramid', 'trad_pyramid', 'boulder_pyramid']:
        old_df = old_data[table_name]
        new_df = new_data[table_name]
        
        results.append({
            'table': table_name,
            'old_records': len(old_df),
            'new_records': len(new_df),
            'diff': len(new_df) - len(old_df),
            'old_null_counts': old_df.isnull().sum().to_dict(),
            'new_null_counts': new_df.isnull().sum().to_dict()
        })
    
    return results

def analyze_send_classification_examples(old_ticks, new_ticks):
    """Show examples of send classification changes with detailed analysis"""
    # Define columns based on actual schema
    columns = ['route_name', 'tick_date', 'discipline', 'send_bool', 'lead_style', 'route_grade']
    
    # Merge old and new data on route_name and tick_date to find differences
    merged = pd.merge(
        old_ticks[columns],
        new_ticks[columns],
        on=['route_name', 'tick_date'],
        suffixes=('_old', '_new')
    )
    
    # Find rows where any classification changed
    changed = merged[
        (merged['send_bool_old'] != merged['send_bool_new']) |
        (merged['discipline_old'] != merged['discipline_new']) |
        ((merged['lead_style_old'] != merged['lead_style_new']) & 
         (~merged['lead_style_old'].isna() | ~merged['lead_style_new'].isna()))
    ]
    
    print("\nDetailed Classification Changes Analysis:")
    print("-" * 80)
    
    # Analyze discipline transitions
    discipline_changes = changed[changed['discipline_old'] != changed['discipline_new']]
    print("\nDiscipline Transition Patterns:")
    transition_counts = discipline_changes.groupby(['discipline_old', 'discipline_new']).size()
    print(transition_counts)
    
    # Analyze lead style updates
    lead_style_changes = changed[
        (changed['lead_style_old'] != changed['lead_style_new']) & 
        (~changed['lead_style_old'].isna() | ~changed['lead_style_new'].isna())
    ]
    print("\nLead Style Update Patterns:")
    lead_style_transitions = lead_style_changes.groupby(['lead_style_old', 'lead_style_new']).size()
    print(lead_style_transitions)
    
    print("\nDetailed Examples of Significant Changes:")
    print("-" * 80)
    for _, row in changed.head(10).iterrows():
        print(f"Route: {row['route_name']} ({row['route_grade_new']})")
        if row['discipline_old'] != row['discipline_new']:
            print(f"Discipline Change: {row['discipline_old']} -> {row['discipline_new']}")
        if row['lead_style_old'] != row['lead_style_new']:
            print(f"Lead Style Change: {row['lead_style_old']} -> {row['lead_style_new']}")
        if row['send_bool_old'] != row['send_bool_new']:
            print(f"Send Status Change: {row['send_bool_old']} -> {row['send_bool_new']}")
        print("-" * 80)

def analyze_length_category_changes(old_ticks, new_ticks):
    """Show examples of length category changes"""
    # Merge old and new data
    merged = pd.merge(
        old_ticks[['route_name', 'tick_date', 'length_category', 'length']],
        new_ticks[['route_name', 'tick_date', 'length_category', 'length']],
        on=['route_name', 'tick_date'],
        suffixes=('_old', '_new')
    )
    
    # Find rows where length category was null in old but not in new
    fixed_nulls = merged[
        merged['length_category_old'].isnull() & 
        merged['length_category_new'].notnull()
    ]
    
    print("\nExamples of Fixed Length Categories:")
    print("-" * 80)
    for _, row in fixed_nulls.head(5).iterrows():
        print(f"Route: {row['route_name']}")
        print(f"Length: {row['length_new']}")
        print(f"Category: None -> {row['length_category_new']}")
        print("-" * 80)

def analyze_characteristic_style_differences(old_data, new_data):
    """Compare route characteristics between old and new data"""
    for pyramid_type in ['sport_pyramid', 'trad_pyramid', 'boulder_pyramid']:
        old_df = old_data[pyramid_type]
        new_df = new_data[pyramid_type]
        
        print(f"\n{pyramid_type} Characteristics:")
        print("-" * 80)
        
        # Compare route characteristics
        if 'route_characteristic' in old_df.columns and 'route_characteristic' in new_df.columns:
            print("\nRoute Characteristic Distribution:")
            print("Old:", old_df['route_characteristic'].value_counts().to_dict())
            print("New:", new_df['route_characteristic'].value_counts().to_dict())
        
        # Compare route styles
        if 'route_style' in old_df.columns and 'route_style' in new_df.columns:
            print("\nRoute Style Distribution:")
            print("Old:", old_df['route_style'].value_counts().to_dict())
            print("New:", new_df['route_style'].value_counts().to_dict())
        print("-" * 80)

def analyze_tr_reclassifications(old_ticks, new_ticks):
    """Analyze routes that were reclassified as top-rope"""
    # Define columns for analysis
    columns = [
        'route_name', 'tick_date', 'discipline', 'send_bool', 
        'lead_style', 'route_grade', 'location'
    ]
    
    # Merge old and new data
    merged = pd.merge(
        old_ticks[columns],
        new_ticks[columns],
        on=['route_name', 'tick_date'],
        suffixes=('_old', '_new')
    )
    
    # Find TR reclassifications
    tr_changes = merged[
        (merged['discipline_new'] == 'tr') & 
        (merged['discipline_old'].isin(['sport', 'trad']))
    ]
    
    print("\nDetailed Analysis of Top-Rope Reclassifications:")
    print("-" * 80)
    
    # Group by original discipline
    for orig_discipline in ['sport', 'trad']:
        discipline_changes = tr_changes[tr_changes['discipline_old'] == orig_discipline]
        
        if len(discipline_changes) > 0:
            print(f"\n{orig_discipline.upper()} to TR Reclassifications:")
            print(f"Total count: {len(discipline_changes)}")
            
            # Show send status impact
            send_changes = discipline_changes.groupby(['send_bool_old', 'send_bool_new']).size()
            print("\nSend Status Changes:")
            print(send_changes)
            
            # Show examples
            print("\nDetailed Examples:")
            for _, row in discipline_changes.head(5).iterrows():
                print("-" * 40)
                print(f"Route: {row['route_name']} ({row['route_grade_new']})")
                print(f"Location: {row['location_new']}")
                print(f"Original: {row['discipline_old']} | {row['lead_style_old']} | Send: {row['send_bool_old']}")
                print(f"Updated:  {row['discipline_new']} | {row['lead_style_new']} | Send: {row['send_bool_new']}")
            print("-" * 80)

def analyze_comprehensive_changes(old_ticks, new_ticks):
    """Provide a comprehensive summary of changes between old and new data"""
    print("\nComprehensive Data Changes Analysis:")
    print("=" * 80)
    
    # Basic record counts
    print(f"\nTotal Records:")
    print(f"Old: {len(old_ticks)} | New: {len(new_ticks)}")
    
    # Merge datasets for comparison
    merged = pd.merge(
        old_ticks,
        new_ticks,
        on=['route_name', 'tick_date'],
        suffixes=('_old', '_new'),
        how='outer'
    )
    
    # Analyze each column
    for col in old_ticks.columns:
        if col in ['route_name', 'tick_date', 'created_at']:  # Skip identifier columns
            continue
            
        old_col = f"{col}_old"
        new_col = f"{col}_new"
        
        if old_col not in merged.columns or new_col not in merged.columns:
            continue
        
        print(f"\n{col.upper()} Changes:")
        print("-" * 40)
        
        # Null value changes
        old_nulls = merged[old_col].isna().sum()
        new_nulls = merged[new_col].isna().sum()
        print(f"Null values: {old_nulls} -> {new_nulls} (Δ: {new_nulls - old_nulls})")
        
        # Value changes
        if merged[old_col].dtype in [object, bool]:
            # For categorical/string columns
            changes = merged[merged[old_col] != merged[new_col]]
            value_counts_old = merged[old_col].value_counts().to_dict()
            value_counts_new = merged[new_col].value_counts().to_dict()
            
            print(f"Changed values: {len(changes)}")
            print("\nValue distribution OLD:")
            print(value_counts_old)
            print("\nValue distribution NEW:")
            print(value_counts_new)
        else:
            # For numeric columns
            changes = merged[merged[old_col] != merged[new_col]]
            print(f"Changed values: {len(changes)}")
            print(f"Mean: {merged[old_col].mean():.2f} -> {merged[new_col].mean():.2f}")
            print(f"Median: {merged[old_col].median():.2f} -> {merged[new_col].median():.2f}")

def main():
    # Get data from both databases
    print("Fetching data from databases...")
    old_data = get_db_data(remote_db_url)
    new_data = get_db_data(local_db_url)
    
    # Comprehensive analysis
    analyze_comprehensive_changes(old_data['user_ticks'], new_data['user_ticks'])
    
    # Analyze TR reclassifications
    analyze_tr_reclassifications(old_data['user_ticks'], new_data['user_ticks'])
    
    # Show examples of send classification changes
    analyze_send_classification_examples(old_data['user_ticks'], new_data['user_ticks'])
    
    # Show examples of length category fixes
    analyze_length_category_changes(old_data['user_ticks'], new_data['user_ticks'])
    
    # Analyze route characteristic and style differences
    analyze_characteristic_style_differences(old_data, new_data)

if __name__ == "__main__":
    main() 