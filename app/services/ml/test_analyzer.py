from app.services.ml.note_analyzer import ClimbingNoteAnalyzer

def main():
    # Initialize analyzer
    analyzer = ClimbingNoteAnalyzer()
    
    # Example climbing notes
    test_notes = [
        "Clean onsight of this classic trad line. The crux comes at the third pitch where you have to make a delicate move around the roof. Protection is good throughout.",
        "Quick sport climb at the local crag. Steep and pumpy with some interesting crimps. Redpointed after a few attempts.",
        "Long multipitch route with amazing exposure. The first three pitches are moderate, but the final headwall is where it gets spicy."
    ]
    
    # Analyze each note
    for note in test_notes:
        print("\nAnalyzing note:", note)
        predictions = analyzer.predict(note, return_confidence=True)
        
        print("\nPredictions:")
        print("Grade:", predictions['grade_info'])
        print("Style:", predictions['style'])
        print("\nConfidence:")
        print("Grade confidence:", predictions['confidence']['grade'])
        print("Style confidence:", predictions['confidence']['style'])
        
        print("\nNote Quality Analysis:")
        quality = analyzer.analyze_note_quality(note)
        print("Length:", quality['length'])
        print("Climbing terms:", quality['climbing_terms'])
        print("Has grade info:", quality['has_grade_info'])
        print("Has beta:", quality['has_beta'])
        print("-" * 80)

if __name__ == "__main__":
    main() 