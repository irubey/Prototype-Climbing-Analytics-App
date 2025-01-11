from lightgbm import LGBMClassifier
import numpy as np
from typing import Tuple, Optional

from .base_predictor import BasePredictor

class SendPredictor(BasePredictor):
    """Predicts probability of sending a climb based on notes"""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize send predictor
        
        Args:
            model_path: Path to saved model. If None, creates new model.
        """
        super().__init__(model_path)
        
        if not model_path:
            self.model = LGBMClassifier(
                objective='binary',
                num_leaves=31,
                learning_rate=0.05,
                n_estimators=100,
                class_weight='balanced',  # Handle imbalanced send/fail ratio
                boost_from_average=True,  # Better probability calibration
                metric='auc'  # Optimize for ROC-AUC
            )
    
    def predict(self, encoded_text: np.ndarray) -> bool:
        """Predict whether climb will be sent
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            bool: True if predicted send, False otherwise
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        # Reshape for single sample prediction
        X = encoded_text.reshape(1, -1)
        return bool(self.model.predict(X)[0])
    
    def predict_proba(self, encoded_text: np.ndarray) -> Tuple[float, float]:
        """Get send probability
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Tuple[float, float]: (no_send_prob, send_prob)
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        X = encoded_text.reshape(1, -1)
        probas = self.model.predict_proba(X)[0]
        return tuple(probas)
    
    def get_confidence(self, encoded_text: np.ndarray) -> float:
        """Get confidence score for prediction
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            float: Confidence score (0-1)
        """
        probas = self.predict_proba(encoded_text)
        return max(probas)  # Higher probability = higher confidence
    
    def get_model_info(self) -> dict:
        """Get send predictor specific information"""
        base_info = super().get_model_info()
        send_info = {
            "prediction_type": "binary",
            "output_classes": ["no_send", "send"],
            "threshold": 0.5  # Default decision threshold
        }
        return {**base_info, **send_info}