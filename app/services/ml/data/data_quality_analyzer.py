class DataQualityAnalyzer:
    def __init__(self):
        from sqlalchemy import create_engine, text
        import pandas as pd
        import os
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv()
        
        # Use local database for development
        db_url = os.getenv('LOCAL_DATABASE_URL')
        self.engine = create_engine(db_url)
        
    def analyze_users(self):
        """Run and display user quality analysis"""
        from app.services.ml.data.data_quality import identify_quality_users
        
        df = identify_quality_users()
        
        print("\n=== User Quality Analysis ===")
        print(f"Total Users: {len(df)}")
        print(f"Quality Users: {df['is_quality_user'].sum()}")
        print("\nQuality Metrics Summary:")
        print(df.describe())
        
        print("\nTop 5 Quality Users:")
        print(df[df['is_quality_user']].head())
        
    def sample_training_data(self):
        """Get and display sample of training data"""
        from app.services.ml.data.data_quality import get_quality_training_data
        
        df = get_quality_training_data()
        
        print("\n=== Training Data Sample ===")
        print(f"Total Records: {len(df)}")
        
        print("\nDistribution by Discipline:")
        print(df['discipline'].value_counts())
        
        print("\nGrade Distribution:")
        print(df.groupby('discipline')['numeric_difficulty'].describe())
        
        print("\nSample Notes:")
        sample = df.sample(5)
        for _, row in sample.iterrows():
            print(f"\nDiscipline: {row['discipline']}")
            print(f"Grade: {row['numeric_difficulty']}")
            print(f"Note: {row['notes'][:100]}...")