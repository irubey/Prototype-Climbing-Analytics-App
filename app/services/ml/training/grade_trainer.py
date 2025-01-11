from typing import Dict, Tuple
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
import logging
import matplotlib.pyplot as plt
import gc
import torch
import faulthandler
import os
import psutil
import xgboost as xgb

from .base_trainer import BaseTrainer
from ..predictors.grade_predictor import GradePredictor
from ...grade_processor import GradeProcessor
from ..data.data_quality import get_quality_training_data

# Enable fault handler
faulthandler.enable()

class GradeTrainer(BaseTrainer):
    """Trainer for grade prediction model"""
    
    def __init__(self, **kwargs):
        """Initialize grade trainer"""
        super().__init__(**kwargs)
        self.grade_processor = GradeProcessor()
        self.predictor = GradePredictor()
        
        # Import db directly from app module
        from app import db
        self.db = db
    
    def load_data(self) -> pd.DataFrame:
        """Load high-quality training data"""
        return get_quality_training_data()
    
    def train(self) -> GradePredictor:
        """Train grade prediction model using GPU acceleration"""
        try:
            # Load quality data
            df = self.load_data()
            self.logger.info(f"Loaded {len(df)} quality training examples")
            
            # Prepare data - no need for aggressive subsampling with RTX 3060 Ti
            X, y = self.prepare_data(df)
            X_train, X_val, y_train, y_val = self.split_data(X, y)
            
            # Convert to float32 and ensure memory layout
            X_train = np.ascontiguousarray(X_train.astype(np.float32))
            X_val = np.ascontiguousarray(X_val.astype(np.float32))
            y_train = np.ascontiguousarray(y_train.astype(np.float32))
            y_val = np.ascontiguousarray(y_val.astype(np.float32))
            
            # Create DMatrix for training
            dtrain = xgb.DMatrix(X_train, label=y_train)
            dval = xgb.DMatrix(X_val, label=y_val)
            
            # Optimized XGBoost parameters for RTX 3060 Ti
            params = {
                'objective': 'reg:squarederror',
                'max_depth': 8,              # Increased for more complex patterns
                'learning_rate': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'tree_method': 'hist',       # Use histogram method
                'device': 'cuda',            # Use CUDA device
                'max_bin': 256,              # Optimal for GPU
                'grow_policy': 'lossguide',
                'max_leaves': 64,            # Increased for better accuracy
                'process_type': 'default',
                'nthread': 6                 # Match i5-10600K cores
            }
            
            # Train model with early stopping
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=200,         # Increased number of rounds
                evals=[(dtrain, 'train'), (dval, 'val')],
                early_stopping_rounds=10,
                verbose_eval=10
            )
            
            # Final evaluation
            y_pred = model.predict(dval)
            metrics = self._calculate_grade_metrics(y_val, y_pred)
            self.log_metrics(metrics, step=0)
            
            # Save model
            self.predictor.model = model
            self.save_model(model, 'grade_model')
            
            # Clean up GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            return self.predictor
            
        except Exception as e:
            self.logger.error(f"Training failed: {str(e)}")
            raise
    
    def _prepare_labels(self, df: pd.DataFrame) -> np.ndarray:
        """Convert grades to binned_codes"""
        return df['binned_code'].values
    
    def _check_memory(self, threshold_mb: int = 4000):
        """Check available memory and cleanup if needed
        
        Args:
            threshold_mb: Memory threshold in MB to trigger cleanup
        """
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.memory_allocated() / 1024 / 1024
            if gpu_memory > threshold_mb:
                self.logger.warning(f"GPU memory usage high ({gpu_memory:.0f}MB). Cleaning up...")
                torch.cuda.empty_cache()
                gpu_memory = torch.cuda.memory_allocated() / 1024 / 1024
                self.logger.info(f"GPU memory after cleanup: {gpu_memory:.0f}MB")
    
    def _tune_learning_rate(self, X_train: np.ndarray, X_val: np.ndarray, 
                           y_train: np.ndarray, y_val: np.ndarray) -> float:
        """Tune learning rate with ultra-conservative memory management"""
        learning_rates = [0.01, 0.05, 0.1]  # Reduced number of learning rates
        best_lr = 0.05  # Default
        best_score = float('inf')
        
        # Ultra-conservative subsample size
        subsample_size = min(200, len(X_train))  # Reduced from 500
        indices = np.random.choice(len(X_train), subsample_size, replace=False)
        
        # Force data to be contiguous and float32
        X_train_sample = np.ascontiguousarray(X_train[indices].astype(np.float32))
        y_train_sample = np.ascontiguousarray(y_train[indices].astype(np.float32))
        X_val_sample = np.ascontiguousarray(X_val[:50].astype(np.float32))  # Smaller validation set
        y_val_sample = np.ascontiguousarray(y_val[:50].astype(np.float32))
        
        # Clear memory before starting
        self._check_memory(threshold_mb=300)
        
        for lr in learning_rates:
            try:
                # Clear memory at start of each iteration
                self._check_memory(threshold_mb=300)
                
                # Create DMatrix objects for XGBoost
                dtrain = xgb.DMatrix(X_train_sample, label=y_train_sample)
                dval = xgb.DMatrix(X_val_sample, label=y_val_sample)
                
                # Ultra-minimal XGBoost parameters
                params = {
                    'objective': 'reg:squarederror',
                    'learning_rate': lr,
                    'max_depth': 2,
                    'subsample': 0.5,
                    'colsample_bytree': 0.5,
                    'tree_method': 'hist',
                    'max_bin': 16,
                    'grow_policy': 'lossguide',
                    'max_leaves': 4,
                    'process_type': 'default',
                    'nthread': 2  # Limit threads
                }
                
                # Train with early stopping using xgb.train
                model = xgb.train(
                    params,
                    dtrain,
                    num_boost_round=10,
                    evals=[(dval, 'val')],
                    early_stopping_rounds=2,
                    verbose_eval=False
                )
                
                # Get validation score
                score = model.best_score
                if score < best_score:
                    best_score = score
                    best_lr = lr
                
                # Explicit cleanup
                del model, dtrain, dval
                self._check_memory(threshold_mb=300)
                
            except Exception as e:
                self.logger.warning(f"Error during learning rate {lr}: {str(e)}")
                self._check_memory(threshold_mb=300)
                continue
            
            # Force garbage collection between iterations
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return best_lr
    
    def _calculate_grade_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate grade-specific metrics"""
        # Calculate regression metrics
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(y_true - y_pred))
        
        # Calculate grade-specific metrics
        grade_accuracy = np.mean(np.abs(y_true - y_pred) <= 1)  # Within 1 grade
        
        return {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'grade_accuracy': grade_accuracy
        }
    
    def _plot_feature_importance(self, model: XGBRegressor):
        """Plot and save feature importance"""
        importance_type = 'weight'  # Can be 'weight', 'gain', or 'cover'
        feature_importance = model.get_booster().get_score(importance_type=importance_type)
        
        # Convert to DataFrame for plotting
        importance_df = pd.DataFrame(
            list(feature_importance.items()),
            columns=['Feature', 'Importance']
        ).sort_values('Importance', ascending=False)
        
        # Plot
        plt.figure(figsize=(10, 6))
        plt.bar(importance_df['Feature'], importance_df['Importance'])
        plt.xticks(rotation=45, ha='right')
        plt.title('Feature Importance (Weight)')
        plt.tight_layout()
        
        # Save plot
        plt.savefig(self.model_dir / 'feature_importance.png')
        plt.close()
    
    def analyze_errors(self, X_val: np.ndarray, y_val: np.ndarray) -> pd.DataFrame:
        """Analyze prediction errors"""
        y_pred = self.predictor.model.predict(X_val)
        
        error_df = pd.DataFrame({
            'true_grade': [self.grade_processor.get_grade_from_code(int(y)) for y in y_val],
            'pred_grade': [self.grade_processor.get_grade_from_code(int(round(y))) for y in y_pred],
            'error': np.abs(y_pred - y_val)
        })
        
        return error_df.sort_values('error', ascending=False)