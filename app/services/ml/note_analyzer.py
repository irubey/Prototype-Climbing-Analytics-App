from typing import Dict, Union, List, Optional
import numpy as np
import logging
from pathlib import Path

from .encoders.text_encoder import ClimbingNoteEncoder
from .predictors.grade_predictor import GradePredictor
from .predictors.style_predictor import StylePredictor

class ClimbingNoteAnalyzer:
    """Analyzes climbing route notes to predict multiple climbing attributes"""
    
    def __init__(self, models_dir: str = 'models'):
        """Initialize the climbing note analyzer
        
        Args:
            models_dir: Directory containing trained models
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.models_dir = Path(models_dir)
        
        # Initialize components
        self.text_encoder = ClimbingNoteEncoder()
        self.grade_predictor = GradePredictor(
            model_path=self.models_dir / 'grade_model.joblib'
        )
        self.style_predictor = StylePredictor(
            model_path=self.models_dir / 'style_model.pt'
        )
    
    def predict(self, notes: Union[str, List[str]], 
                return_confidence: bool = False) -> Dict:
        """Analyze climbing notes and make predictions
        
        Args:
            notes: Single note or list of notes
            return_confidence: Whether to include prediction confidences
        Returns:
            Dictionary of predictions
        """
        # Handle single note
        if isinstance(notes, str):
            return self._predict_single(notes, return_confidence)
        
        # Handle batch of notes
        return self._predict_batch(notes, return_confidence)
    
    def _predict_single(self, note: str, 
                       return_confidence: bool = False) -> Dict:
        """Make predictions for a single note"""
        self.logger.info(f"Analyzing note: {note[:100]}...")
        
        # Encode text using encode_batch for single note
        encoded_text = self.text_encoder.encode_batch([note])[0]
        
        # Get predictions
        predictions = {
            'grade': self.grade_predictor.predict(encoded_text),
            'style': self.style_predictor.predict(encoded_text)
        }
        
        # Add human-readable grade
        predictions['grade_info'] = self.grade_predictor.decode_grade(
            predictions['grade']
        )
        
        # Add confidences if requested
        if return_confidence:
            predictions['confidence'] = {
                'grade': self.grade_predictor.get_confidence(encoded_text),
                'style': self.style_predictor.get_confidence(encoded_text)
            }
        
        return predictions
    
    def _predict_batch(self, notes: List[str], 
                      return_confidence: bool = False) -> List[Dict]:
        """Make predictions for multiple notes"""
        self.logger.info(f"Analyzing batch of {len(notes)} notes...")
        
        # Encode all notes using encode_batch
        encoded_texts = self.text_encoder.encode_batch(notes)
        
        # Get predictions for all notes
        predictions = []
        for i, encoded_text in enumerate(encoded_texts):
            pred = {
                'grade': self.grade_predictor.predict(encoded_text),
                'style': self.style_predictor.predict(encoded_text)
            }
            
            # Add human-readable grade
            pred['grade_info'] = self.grade_predictor.decode_grade(
                pred['grade']
            )
            
            # Add confidences if requested
            if return_confidence:
                pred['confidence'] = {
                    'grade': self.grade_predictor.get_confidence(encoded_text),
                    'style': self.style_predictor.get_confidence(encoded_text)
                }
            
            predictions.append(pred)
        
        return predictions
    
    def analyze_note_quality(self, note: str) -> Dict:
        """Analyze the quality of a climbing note
        
        Args:
            note: Climbing note to analyze
        Returns:
            Dictionary with quality metrics
        """
        # Get climbing term importance
        term_importance = self.text_encoder.get_climbing_term_importance(note)
        
        # Calculate basic metrics
        quality_metrics = {
            'length': len(note),
            'climbing_terms': len(term_importance),
            'total_importance': sum(term_importance.values()),
            'has_grade_info': any(term in note.lower() 
                                for term in ['5.', 'v', 'wi', 'aid']),
            'has_beta': 'beta' in note.lower()
        }
        
        # Add term breakdown
        quality_metrics['important_terms'] = term_importance
        
        return quality_metrics
    
    def get_model_info(self) -> Dict:
        """Get information about all models
        
        Returns:
            Dictionary with model information
        """
        return {
            'grade_model': self.grade_predictor.get_model_info(),
            'style_model': self.style_predictor.get_model_info()
        }