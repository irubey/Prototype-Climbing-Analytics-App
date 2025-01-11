from xgboost import XGBRegressor
import numpy as np
from typing import Dict, Optional, Tuple, Union, List
from enum import Enum

from .base_predictor import BasePredictor

class DisciplineCodes(Enum):
    """First digit of binned_code indicating discipline"""
    ROUTE = 0      # Regular routes (trad and sport) (5.x)
    BOULDER = 1    # Boulder problems (V-grades)
    ICE = 2        # Ice climbing (WI)
    MIXED = 3      # Mixed climbing (M)
    AID = 4        # Aid climbing (A)
    TRAD = 5       # Traditional (3rd, 4th, 5th)
    SNOW = 6       # Snow grades
    CLEAN = 7      # Clean aid (C)
    ALPINE = 8     # Alpine ice (AI)

class GradePredictor(BasePredictor):
    """Predicts climbing grade codes from notes"""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize grade predictor"""
        super().__init__(model_path)
        
        # Load grade mappings
        from app.services.grade_processor import GradeProcessor
        self.grade_processor = GradeProcessor()
        
        if not model_path:
            self.model = XGBRegressor(
                objective='reg:squarederror',
                max_depth=6,
                n_estimators=200,
                learning_rate=0.05,
                min_child_weight=2,
                subsample=0.8,
                colsample_bytree=0.8,
                gamma=1,
                tree_method='hist',  # Use histogram method for better memory efficiency
                max_bin=64  # Reduce memory usage
            )
        else:
            self.model = self.load_model(model_path)
    
    def predict(self, encoded_text: np.ndarray, discipline: str = None) -> int:
        """Predict climbing grade code
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
            discipline: Optional discipline to force prediction within
        Returns:
            int: binned_code (e.g. 17 for 5.12-, 102 for V0)
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        X = encoded_text.reshape(1, -1)
        predicted_code = int(round(self.model.predict(X)[0]))
        
        if discipline:
            # Ensure prediction is within discipline's range
            ranges = self._get_discipline_ranges()
            discipline_range = ranges.get(discipline.lower())
            if discipline_range:
                min_code, max_code = discipline_range
                predicted_code = max(min_code, min(predicted_code, max_code))
        
        return predicted_code
    
    def predict_proba(self, encoded_text: np.ndarray) -> np.ndarray:
        """Get prediction probabilities/confidence
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            np.ndarray: Raw model output before rounding
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        X = encoded_text.reshape(1, -1)
        return self.model.predict(X)
    
    def get_confidence(self, encoded_text: np.ndarray) -> float:
        """Get confidence score for prediction
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            float: Confidence score between 0 and 1
        """
        # For regression, we use a simple heuristic based on prediction variance
        raw_pred = self.predict_proba(encoded_text)[0]
        pred_int = int(round(raw_pred))
        
        # Convert difference to confidence score (closer to predicted integer = higher confidence)
        confidence = 1.0 - min(abs(raw_pred - pred_int), 1.0)
        return confidence
    
    def decode_grade(self, binned_code: int) -> Dict[str, str]:
        """Convert binned_code to human-readable grade
        
        Args:
            binned_code: Integer grade code
        Returns:
            Dict with grade information
        """
        grade = self.grade_processor.get_grade_from_code(binned_code)
        discipline = self._get_discipline_from_code(binned_code)
        
        return {
            'grade': grade,
            'discipline': discipline,
            'binned_code': binned_code
        }
    
    def _get_discipline_ranges(self) -> Dict[str, Tuple[int, int]]:
        """Get valid grade ranges for each discipline"""
        return {
            'sport': (1, 28),       # 5.0 to 5.15+
            'boulder': (101, 120),  # V-easy to V18
            'ice': (201, 208),      # WI1 to WI8
            'mixed': (301, 319),    # M1 to M19
            'aid': (401, 405),      # A0 to A4
            'trad': (501, 503),     # 3rd to 5th
            'snow': (601, 601),     # Snow
            'clean': (701, 705),    # C0 to C4
            'alpine': (801, 805)    # AI0 to AI4
        }
    
    def _get_discipline_from_code(self, binned_code: int) -> str:
        """Determine discipline from binned_code"""
        discipline_code = binned_code // 100
        disciplines = {
            0: 'route',
            1: 'boulder',
            2: 'ice',
            3: 'mixed',
            4: 'aid',
            5: 'trad',
            6: 'snow',
            7: 'clean',
            8: 'alpine'
        }
        return disciplines.get(discipline_code, 'unknown')