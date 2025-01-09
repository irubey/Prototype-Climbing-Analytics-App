import pandas as pd
from app.services.climb_classifier import ClimbClassifier
from app.services.pyramid_builder import PyramidBuilder

# Create test data
test_data = {
    'discipline': ['boulder'] * 6,
    'style': ['Send', 'Flash', 'Attempt', None, 'Send', 'Flash'],
    'lead_style': [None] * 6,
    'route_name': [f'Boulder {i}' for i in range(1, 7)],
    'location': ['Test Area'] * 6,
    'tick_date': ['2024-01-08'] * 6,
    'route_grade': ['V3', 'V2', 'V1', 'V0', 'V4', 'V5'],
    'binned_code': [103, 102, 101, 100, 104, 105],  # Assuming V0=100, V1=101, etc.
    'length': [10] * 6,
    'pitches': [1] * 6,
    'length_category': ['short'] * 6,  # All boulders are short
    'notes': [''] * 6,  # Empty notes
    'route_type': ['Boulder'] * 6  # All are boulder type
}

df = pd.DataFrame(test_data)

# First classify sends
classifier = ClimbClassifier()
df['send_bool'] = classifier.classify_sends(df)

# Then build pyramid
builder = PyramidBuilder()
_, _, boulder_pyramid = builder.build_all_pyramids(df)

print("\nOriginal Data:")
print("-" * 80)
for _, row in df.iterrows():
    print(f"Route: {row['route_name']}")
    print(f"Grade: {row['route_grade']}")
    print(f"Style: {row['style']}")
    print(f"Send: {row['send_bool']}")
    print("-" * 80)

print("\nBoulder Pyramid:")
print("-" * 80)
if boulder_pyramid.empty:
    print("No sends in pyramid")
else:
    for _, row in boulder_pyramid.iterrows():
        print(f"Route: {row['route_name']}")
        print(f"Grade: {row['route_grade']}")
        print("-" * 80) 