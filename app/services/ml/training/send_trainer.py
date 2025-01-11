from typing import Dict, Tuple
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.calibration import CalibratedClassifierCV
from imblearn.over_sampling import SMOTE
import joblib

from .base_trainer import BaseTrainer
from ..predictors.send_predictor import SendPredictor
from ..data.data_quality import get_quality_training_data

class SendTrainer(BaseTrainer):
    """Trainer for send prediction model"""
    
    def __init__(self, **kwargs):
        """Initialize send trainer"""
        super().__init__(**kwargs)
        self.predictor = SendPredictor()
        
        # Import db directly from app module
        from app import db
        self.db = db
    
    def load_data(self) -> pd.DataFrame:
        """Load high-quality training data"""
        return get_quality_training_data()
    
    def _prepare_labels(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare binary send labels
        
        Args:
            df: DataFrame with 'send_bool' column
        Returns:
            numpy array of binary labels
        """
        return df['send_bool'].values.astype(int)
    
    def train(self) -> SendPredictor:
        """Train send prediction model
        
        Returns:
            Trained SendPredictor
        """
        # Load and prepare data
        df = self.load_data()
        X, y = self.prepare_data(df)
        X_train, X_val, y_train, y_val = self.split_data(X, y)
        
        # Balance training data using SMOTE
        self.logger.info("Balancing training data with SMOTE...")
        smote = SMOTE(random_state=self.random_state)
        X_train_balanced, y_train_balanced = smote.fit_resample(X_train, y_train)
        
        # Initialize model
        model = LGBMClassifier(
            objective='binary',
            num_leaves=31,
            learning_rate=0.05,
            n_estimators=100,
            class_weight='balanced',
            boost_from_average=True,
            random_state=self.random_state,
            force_col_wise=True,  # Better for our wide feature matrix
            metric=['auc', 'binary_logloss'],  # Monitor multiple metrics
            verbose=-1,  # Less verbose output
            feature_fraction=0.8,  # Feature subsampling for better generalization
            bagging_fraction=0.8,  # Row subsampling
            bagging_freq=5,  # Perform bagging every 5 iterations
            min_child_samples=20,  # Minimum samples per leaf for robustness
            path_smooth=1.0,  # Smoothing to prevent overfitting
        )
        
        # Train with early stopping
        model.fit(
            X_train_balanced, y_train_balanced,
            eval_set=[(X_train_balanced, y_train_balanced), (X_val, y_val)],
            eval_names=['train', 'valid'],
            eval_metric=['auc', 'binary_logloss'],
            early_stopping_rounds=10,
            verbose=50  # Print every 50 iterations
        )
        
        # Calibrate probabilities
        self.logger.info("Calibrating prediction probabilities...")
        calibrated_model = CalibratedClassifierCV(
            model, 
            cv='prefit',
            method='isotonic'
        )
        calibrated_model.fit(X_val, y_val)
        
        # Evaluate
        y_pred = calibrated_model.predict(X_val)
        y_prob = calibrated_model.predict_proba(X_val)[:, 1]
        metrics = self._calculate_send_metrics(y_val, y_pred, y_prob)
        self.log_metrics(metrics, step=0)
        
        # Save model
        self.predictor.model = calibrated_model
        self.save_model(calibrated_model, 'send_model')
        
        return self.predictor
    
    def _calculate_send_metrics(self, y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> Dict[str, float]:
        """Calculate send-specific metrics
        
        Args:
            y_true: True send/no-send labels
            y_pred: Predicted labels
            y_prob: Predicted probabilities
        Returns:
            Dictionary of metrics
        """
        # Classification metrics
        base_metrics = self.evaluate(y_true, y_pred)
        
        # Add probability-based metrics
        prob_metrics = {
            'auc_roc': roc_auc_score(y_true, y_prob),
            'avg_precision': average_precision_score(y_true, y_prob)
        }
        
        # Calculate confidence calibration
        confidence_bins = np.linspace(0, 1, 11)
        bin_accuracies = []
        for i in range(len(confidence_bins)-1):
            mask = (y_prob >= confidence_bins[i]) & (y_prob < confidence_bins[i+1])
            if np.any(mask):
                bin_accuracies.append(np.mean(y_true[mask] == y_pred[mask]))
        
        calibration_metrics = {
            'calibration_score': np.mean(np.abs(np.array(bin_accuracies) - 
                                              (confidence_bins[1:] + confidence_bins[:-1])/2))
        }
        
        return {**base_metrics, **prob_metrics, **calibration_metrics}
    
    def analyze_errors(self, X_val: np.ndarray, y_val: np.ndarray) -> pd.DataFrame:
        """Analyze prediction errors
        
        Args:
            X_val: Validation features
            y_val: True labels
        Returns:
            DataFrame with error analysis
        """
        y_pred = self.predictor.model.predict(X_val)
        y_prob = self.predictor.model.predict_proba(X_val)[:, 1]
        
        error_df = pd.DataFrame({
            'true_send': y_val,
            'predicted_send': y_pred,
            'confidence': y_prob,
            'error': y_val != y_pred
        })
        
        return error_df[error_df['error']].sort_values('confidence', ascending=False)