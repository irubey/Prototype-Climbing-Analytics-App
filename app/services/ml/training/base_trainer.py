from typing import Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import logging
from pathlib import Path
import json
from datetime import datetime
import joblib
import os
import gc
import torch

from ..data.data_quality import get_quality_training_data
from ..encoders.text_encoder import ClimbingNoteEncoder

class BaseTrainer:
    """Base class for all model trainers"""
    
    def __init__(self, 
                 test_size: float = 0.2,
                 random_state: int = 42,
                 model_dir: str = 'models',
                 batch_size: int = 32,
                 cache_dir: str = 'cache'):
        """Initialize trainer
        
        Args:
            test_size: Fraction of data to use for validation
            random_state: Random seed for reproducibility
            model_dir: Directory to save models and metrics
            batch_size: Size of batches for data processing
            cache_dir: Directory to save cached encodings
        """
        self.test_size = test_size
        self.random_state = random_state
        self.model_dir = Path(model_dir)
        self.cache_dir = Path(cache_dir)
        self.batch_size = batch_size
        
        # Create directories
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.encoder = ClimbingNoteEncoder()
        self.metrics_history = []
        
    def load_data(self) -> pd.DataFrame:
        """Load quality training data from database"""
        self.logger.info("Loading training data...")
        return get_quality_training_data()
    
    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, Any]:
        """Prepare features and labels
        
        Args:
            df: DataFrame with notes and labels
        Returns:
            Tuple of (features, labels)
        """
        # Check cache first
        cache_file = self.cache_dir / f"{self.__class__.__name__}_encoded_data.npz"
        if cache_file.exists():
            self.logger.info("Loading cached encoded data...")
            # Load in chunks to manage memory
            with np.load(cache_file, allow_pickle=True, mmap_mode='r') as data:
                features = data['features'].astype(np.float32)  # Convert to float32 to save memory
                labels = data['labels']
                return features, labels
        
        self.logger.info("Encoding notes in batches...")
        
        # Process in smaller batches to manage memory
        batch_size = min(32, len(df))  # Use smaller batch size
        features = []
        
        try:
            for i in range(0, len(df), batch_size):
                # Clear memory before each batch
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                batch_df = df.iloc[i:i + batch_size]
                batch_encodings = self.encoder.encode_batch(
                    batch_df['notes'].values, 
                    batch_size=4  # Use even smaller batches for encoding
                )
                features.append(batch_encodings)
                
                # Clear memory after each batch
                if hasattr(self.encoder, 'clear_cache'):
                    self.encoder.clear_cache()
                
                # Log progress
                if (i + 1) % (batch_size * 5) == 0:
                    self.logger.info(f"Processed {i + 1}/{len(df)} samples...")
            
            # Stack features and convert to float32
            X = np.vstack(features).astype(np.float32)
            y = self._prepare_labels(df)
            
            # Save to cache
            self.logger.info("Saving encoded data to cache...")
            np.savez_compressed(cache_file, features=X, labels=y)
            
            return X, y
            
        except Exception as e:
            self.logger.error(f"Error during data preparation: {str(e)}")
            raise
    
    def split_data(self, X: np.ndarray, y: Any) -> Tuple[np.ndarray, np.ndarray, Any, Any]:
        """Split data into train/validation sets
        
        Args:
            X: Feature matrix
            y: Labels
        Returns:
            Tuple of (X_train, X_val, y_train, y_val)
        """
        return train_test_split(X, y, test_size=self.test_size, 
                              random_state=self.random_state)
    
    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate basic classification metrics
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
        Returns:
            Dictionary of metrics
        """
        accuracy = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='weighted'
        )
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }
    
    def log_metrics(self, metrics: Dict[str, float], step: int):
        """Log metrics to file
        
        Args:
            metrics: Dictionary of metric names and values
            step: Training step/epoch
        """
        metrics['step'] = step
        metrics['timestamp'] = datetime.now().isoformat()
        self.metrics_history.append(metrics)
        
        # Save metrics
        metrics_file = self.model_dir / f"{self.__class__.__name__}_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics_history, f, indent=2)
    
    def save_model(self, model: Any, name: str):
        """Save model to file
        
        Args:
            model: Trained model
            name: Model name
        """
        model_file = self.model_dir / f"{name}.joblib"
        joblib.dump(model, model_file)
    
    def _prepare_labels(self, df: pd.DataFrame) -> Any:
        """Prepare labels from DataFrame
        
        To be implemented by child classes
        """
        raise NotImplementedError