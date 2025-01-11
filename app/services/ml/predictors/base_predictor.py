from abc import ABC, abstractmethod
import joblib
import numpy as np
import logging
from typing import Any, Dict, Optional, Union
from pathlib import Path

class BasePredictor(ABC):
    """Base class for all climbing predictors"""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize the base predictor
        
        Args:
            model_path: Path to saved model file. If None, creates new model.
        """
        self.model = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load model if path provided
        if model_path:
            self.load_model(model_path)
    
    @abstractmethod
    def predict(self, encoded_text: np.ndarray) -> Any:
        """Make prediction from encoded text
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        """
        pass
    
    @abstractmethod
    def predict_proba(self, encoded_text: np.ndarray) -> np.ndarray:
        """Get prediction probabilities/confidence
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        """
        pass
    
    def validate_input(self, encoded_text: np.ndarray) -> bool:
        """Validate encoded text input
        
        Args:
            encoded_text: RoBERTa encoded text
        Returns:
            bool: True if valid
        Raises:
            ValueError: If input invalid
        """
        if not isinstance(encoded_text, np.ndarray):
            raise ValueError("Input must be numpy array")
        
        expected_shape = (768,)  # RoBERTa base output size
        if encoded_text.shape != expected_shape:
            raise ValueError(f"Input shape must be {expected_shape}, got {encoded_text.shape}")
        
        return True
    
    def save_model(self, path: str) -> None:
        """Save model to disk
        
        Args:
            path: Path to save model
        """
        if self.model is None:
            raise ValueError("No model to save")
            
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        self.logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str) -> None:
        """Load model from disk
        
        Args:
            path: Path to load model from
        """
        if not Path(path).exists():
            raise FileNotFoundError(f"Model file not found: {path}")
            
        self.model = joblib.load(path)
        self.logger.info(f"Model loaded from {path}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information
        
        Returns:
            Dict with model info
        """
        return {
            "model_type": type(self.model).__name__,
            "predictor_type": self.__class__.__name__,
            "input_shape": (768,),  # RoBERTa base
            "parameters": getattr(self.model, "get_params", lambda: {})()
        }
    
    def _check_model_loaded(self) -> None:
        """Verify model is loaded
        
        Raises:
            ValueError if no model loaded
        """
        if self.model is None:
            raise ValueError("No model loaded. Load model before prediction.")
