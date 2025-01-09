import pandas as pd
from app.services.climb_classifier import ClimbClassifier

# Create test data
test_data = {
    'discipline': ['boulder', 'boulder', 'boulder', 'boulder', 'sport', 'trad'],
    'style': ['Send', 'Flash', 'Attempt', None, 'Lead', 'Lead'],
    'lead_style': [None, None, None, None, 'Redpoint', 'Onsight'],
    'route_name': ['Test Boulder 1', 'Test Boulder 2', 'Test Boulder 3', 'Test Boulder 4', 'Sport Route', 'Trad Route']
}

df = pd.DataFrame(test_data)
classifier = ClimbClassifier()

# Classify sends
df['send_bool'] = classifier.classify_sends(df)

# Print results
print("\nTest Results:")
print("-" * 80)
for _, row in df.iterrows():
    print(f"Route: {row['route_name']}")
    print(f"Discipline: {row['discipline']}")
    print(f"Style: {row['style']}")
    print(f"Lead Style: {row['lead_style']}")
    print(f"Send: {row['send_bool']}")
    print("-" * 80) 