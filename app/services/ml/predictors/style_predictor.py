import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional, Union
from enum import Enum

from .base_predictor import BasePredictor

class StyleCategories(Enum):
    """Categories for style prediction from database"""
    DISCIPLINE = ['sport', 'trad', 'boulder', 'tr']
    LEAD_STYLE = ['Redpoint', 'Flash', 'Onsight', 'Pinkpoint']
    LENGTH = ['short', 'medium', 'long', 'multipitch']
    DIFFICULTY = ['Project', 'Tier 2', 'Tier 3', 'Base Volume']

class StylePredictor(BasePredictor):
    """Predicts climbing style attributes from notes"""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize style predictor
        
        Args:
            model_path: Path to saved model. If None, creates new model.
        """
        super().__init__(model_path)
        
        if not model_path:
            # Multi-head neural network for style predictions
            self.model = StyleNetwork(
                input_size=768,  # RoBERTa embedding size
                hidden_size=256,
                num_disciplines=len(StyleCategories.DISCIPLINE.value),
                num_lead_styles=len(StyleCategories.LEAD_STYLE.value),
                num_lengths=len(StyleCategories.LENGTH.value)
            )
    
    def predict(self, encoded_text: np.ndarray) -> Dict[str, str]:
        """Predict climbing styles
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict with predictions for each style category
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        # Convert to tensor and get predictions
        X = torch.FloatTensor(encoded_text).unsqueeze(0)
        with torch.no_grad():
            discipline_logits, lead_style_logits, length_logits = self.model(X)
        
        # Get highest probability predictions
        predictions = {
            'discipline': StyleCategories.DISCIPLINE.value[discipline_logits.argmax().item()],
            'lead_style': StyleCategories.LEAD_STYLE.value[lead_style_logits.argmax().item()],
            'length': StyleCategories.LENGTH.value[length_logits.argmax().item()]
        }
        
        return predictions
    
    def predict_proba(self, encoded_text: np.ndarray) -> Dict[str, List[float]]:
        """Get probabilities for each style category
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict with probabilities for each category
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        X = torch.FloatTensor(encoded_text).unsqueeze(0)
        with torch.no_grad():
            discipline_logits, lead_style_logits, length_logits = self.model(X)
            
        # Convert logits to probabilities
        softmax = nn.Softmax(dim=1)
        probabilities = {
            'discipline': softmax(discipline_logits)[0].tolist(),
            'lead_style': softmax(lead_style_logits)[0].tolist(),
            'length': softmax(length_logits)[0].tolist()
        }
        
        return probabilities
    
    def get_confidence(self, encoded_text: np.ndarray) -> Dict[str, float]:
        """Get confidence scores for each prediction
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict with confidence scores for each category
        """
        probas = self.predict_proba(encoded_text)
        return {
            category: max(probs) 
            for category, probs in probas.items()
        }

class StyleNetwork(nn.Module):
    """Multi-head neural network for style prediction"""
    
    def __init__(self, input_size: int, hidden_size: int, 
                 num_disciplines: int, num_lead_styles: int, num_lengths: int):
        super().__init__()
        
        self.shared = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Separate heads for each prediction
        self.discipline_head = nn.Linear(hidden_size, num_disciplines)
        self.lead_style_head = nn.Linear(hidden_size, num_lead_styles)
        self.length_head = nn.Linear(hidden_size, num_lengths)
    
    def forward(self, x):
        """Forward pass through network"""
        shared_features = self.shared(x)
        return (
            self.discipline_head(shared_features),
            self.lead_style_head(shared_features),
            self.length_head(shared_features)
        )