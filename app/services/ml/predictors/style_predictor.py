import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional, Union
from enum import Enum
from ..config import get_device, clear_gpu_cache
from ..encoders.text_encoder import ClimbingNoteEncoder
from pathlib import Path
import logging

from .base_predictor import BasePredictor

class StyleCategories(Enum):
    """Categories for style prediction from database"""
    DISCIPLINE = ['sport', 'trad', 'boulder', 'tr']
    LEAD_STYLE = ['Redpoint', 'Flash', 'Onsight', 'Pinkpoint']
    LENGTH_CATEGORY = ['short', 'medium', 'long', 'multipitch']
    DIFFICULTY = ['Project', 'Tier 2', 'Tier 3', 'Base Volume']

class StylePredictor(BasePredictor):
    """Predicts climbing style attributes from notes"""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize style predictor
        
        Args:
            model_path: Path to saved model. If None, creates new model.
        """
        self.model = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.text_encoder = ClimbingNoteEncoder()
        
        # Get optimal device
        self.device = get_device()
        
        if model_path:
            self.load_model(model_path)
        else:
            # Multi-head neural network for style predictions
            self.model = StyleNetwork(
                input_size=768,  # RoBERTa embedding size
                hidden_size=256,
                num_disciplines=len(StyleCategories.DISCIPLINE.value),
                num_lead_styles=len(StyleCategories.LEAD_STYLE.value),
                num_length_categories=len(StyleCategories.LENGTH_CATEGORY.value)
            ).to(self.device)
            
            # Enable CUDA optimizations if available
            if torch.cuda.is_available():
                self.model = torch.jit.script(self.model)  # JIT compilation
                torch.backends.cudnn.benchmark = True
    
    def save_model(self, path: str) -> None:
        """Save PyTorch model to disk
        
        Args:
            path: Path to save model
        """
        if self.model is None:
            raise ValueError("No model to save")
            
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save model architecture first
        model_config = {
            'input_size': self.model.input_size,
            'hidden_size': self.model.hidden_size,
            'num_disciplines': self.model.num_disciplines,
            'num_lead_styles': self.model.num_lead_styles,
            'num_length_categories': self.model.num_length_categories
        }
        
        # Save both config and state dict
        torch.save({
            'model_config': model_config,
            'model_state_dict': self.model.state_dict()
        }, path, _use_new_zipfile_serialization=True)
        
        self.logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str) -> None:
        """Load PyTorch model from disk
        
        Args:
            path: Path to load model from
        """
        if not Path(path).exists():
            raise FileNotFoundError(f"Model file not found: {path}")
            
        try:
            # Load checkpoint
            checkpoint = torch.load(path, map_location=self.device)
            
            # Get model config
            if 'model_config' in checkpoint:
                config = checkpoint['model_config']
            else:
                # Try direct access for backward compatibility
                config = {
                    'input_size': checkpoint['input_size'],
                    'hidden_size': checkpoint['hidden_size'],
                    'num_disciplines': checkpoint['num_disciplines'],
                    'num_lead_styles': checkpoint['num_lead_styles'],
                    'num_length_categories': checkpoint['num_length_categories']
                }
            
            # Create new model instance
            self.model = StyleNetwork(**config).to(self.device)
            
            # Load state dict
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
            else:
                raise KeyError("Could not find model state dict in checkpoint")
                
            self.model.load_state_dict(state_dict)
            self.model.eval()
            
            # Enable CUDA optimizations if available
            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True
                
            self.logger.info(f"Model loaded successfully from {path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise
    
    @property
    def discipline_labels(self) -> List[str]:
        return StyleCategories.DISCIPLINE.value
        
    @property
    def lead_style_labels(self) -> List[str]:
        return StyleCategories.LEAD_STYLE.value
        
    @property
    def length_labels(self) -> List[str]:
        return StyleCategories.LENGTH_CATEGORY.value

    def _get_prediction(self, logits: torch.Tensor, labels: List[str]) -> str:
        """Get prediction from logits
        
        Args:
            logits: Raw model outputs
            labels: List of class labels
        Returns:
            Predicted class label
        """
        probs = torch.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).item()
        return labels[pred_idx]

    def _get_confidence(self, logits: torch.Tensor) -> float:
        """Get confidence score from logits
        
        Args:
            logits: Raw model outputs
        Returns:
            Confidence score between 0 and 1
        """
        probs = torch.softmax(logits, dim=1)
        return torch.max(probs, dim=1)[0].item()

    def predict(self, encoded_text: np.ndarray) -> Dict[str, str]:
        """Predict climbing style attributes
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict with style predictions
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        # Convert to tensor
        X = torch.from_numpy(encoded_text).float().to(self.device)
        
        # Get predictions with autocast
        with torch.no_grad(), torch.amp.autocast('cuda') if torch.cuda.is_available() else torch.no_grad():
            outputs = self.model(X.unsqueeze(0))
            
        # Convert logits to predictions
        return {
            'discipline': self._get_prediction(outputs['discipline'], self.discipline_labels),
            'lead_style': self._get_prediction(outputs['lead_style'], self.lead_style_labels),
            'length_category': self._get_prediction(outputs['length_category'], self.length_labels)
        }
        
    def get_confidence(self, encoded_text: np.ndarray) -> Dict[str, float]:
        """Get confidence scores for predictions
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict with confidence scores
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        # Convert to tensor
        X = torch.from_numpy(encoded_text).float().to(self.device)
        
        # Get predictions with autocast
        with torch.no_grad(), torch.amp.autocast('cuda') if torch.cuda.is_available() else torch.no_grad():
            outputs = self.model(X.unsqueeze(0))
            
        # Get confidence scores using softmax
        return {
            'discipline': self._get_confidence(outputs['discipline']),
            'lead_style': self._get_confidence(outputs['lead_style']),
            'length_category': self._get_confidence(outputs['length_category'])
        }

    def predict_proba(self, encoded_text: np.ndarray) -> Dict[str, np.ndarray]:
        """Get prediction probabilities for each category
        
        Args:
            encoded_text: RoBERTa encoded text (768,)
        Returns:
            Dict mapping categories to probability arrays
        """
        self._check_model_loaded()
        self.validate_input(encoded_text)
        
        # Convert to tensor
        X = torch.from_numpy(encoded_text).float().to(self.device)
        
        # Get predictions with autocast
        with torch.no_grad(), torch.amp.autocast('cuda') if torch.cuda.is_available() else torch.no_grad():
            outputs = self.model(X.unsqueeze(0))
            
        # Convert logits to probabilities using softmax
        softmax = nn.Softmax(dim=1)
        return {
            'discipline': softmax(outputs['discipline']).cpu().numpy(),
            'lead_style': softmax(outputs['lead_style']).cpu().numpy(),
            'length_category': softmax(outputs['length_category']).cpu().numpy()
        }

class StyleNetwork(nn.Module):
    """Multi-head neural network for style predictions"""
    
    def __init__(self, input_size: int, hidden_size: int,
                 num_disciplines: int, num_lead_styles: int, num_length_categories: int):
        """Initialize network
        
        Args:
            input_size: Size of input features
            hidden_size: Size of hidden layer
            num_disciplines: Number of discipline classes
            num_lead_styles: Number of lead style classes 
            num_length_categories: Number of length category classes
        """
        super().__init__()
        
        # Store dimensions as instance variables for serialization
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_disciplines = num_disciplines
        self.num_lead_styles = num_lead_styles
        self.num_length_categories = num_length_categories
        
        # Shared layers
        self.shared = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.BatchNorm1d(hidden_size)
        )
        
        # Separate heads for each category
        self.discipline_head = nn.Linear(hidden_size, num_disciplines)
        self.lead_style_head = nn.Linear(hidden_size, num_lead_styles)
        self.length_category_head = nn.Linear(hidden_size, num_length_categories)
        
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, input_size)
            
        Returns:
            Dictionary mapping category names to logits
        """
        shared_features = self.shared(x)
        
        return {
            'discipline': self.discipline_head(shared_features),
            'lead_style': self.lead_style_head(shared_features),
            'length_category': self.length_category_head(shared_features)
        }
    
    def __getstate__(self):
        """Return state values to be pickled."""
        return {
            'model_state': self.state_dict(),
            'metadata': {
                'input_size': self.input_size,
                'hidden_size': self.hidden_size,
                'num_disciplines': self.num_disciplines,
                'num_lead_styles': self.num_lead_styles,
                'num_length_categories': self.num_length_categories
            }
        }

    def __setstate__(self, state):
        """Restore state from the unpickled state values."""
        self.__init__(
            state['metadata']['input_size'],
            state['metadata']['hidden_size'],
            state['metadata']['num_disciplines'],
            state['metadata']['num_lead_styles'],
            state['metadata']['num_length_categories']
        )
        self.load_state_dict(state['model_state'])