from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import logging

from .base_trainer import BaseTrainer
from ..predictors.style_predictor import StylePredictor, StyleCategories
from ..data.data_quality import get_quality_training_data

class StyleTrainer(BaseTrainer):
    """Trainer for style prediction model"""
    
    def __init__(self, batch_size: int = 32, num_epochs: int = 10, 
                 learning_rate: float = 0.001, label_smoothing: float = 0.1, **kwargs):
        """Initialize style trainer
        
        Args:
            batch_size: Training batch size
            num_epochs: Number of training epochs
            learning_rate: Initial learning rate
            label_smoothing: Label smoothing factor for loss
        """
        super().__init__(**kwargs)
        self.batch_size = batch_size
        self.num_epochs = num_epochs
        self.learning_rate = learning_rate
        self.label_smoothing = label_smoothing
        self.predictor = StylePredictor()
        self.label_encoders = {
            'discipline': LabelEncoder(),
            'lead_style': LabelEncoder(),
            'length': LabelEncoder()
        }
        
        # Import db directly from app module
        from app import db
        self.db = db
    
    def load_data(self) -> pd.DataFrame:
        """Load high-quality training data"""
        return get_quality_training_data()
    
    def _prepare_labels(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Prepare categorical labels
        
        Args:
            df: DataFrame with style columns
        Returns:
            Dict of encoded labels for each category
        """
        encoded_labels = {}
        for category in self.label_encoders:
            # Fit encoder on valid categories from StyleCategories
            valid_categories = StyleCategories[category.upper()].value
            self.label_encoders[category].fit(valid_categories)
            # Transform data
            encoded_labels[category] = self.label_encoders[category].transform(df[category])
        return encoded_labels
    
    def train(self) -> StylePredictor:
        """Train style prediction model
        
        Returns:
            Trained StylePredictor
        """
        # Load and prepare data
        df = self.load_data()
        X, y_dict = self.prepare_data(df)
        
        # Convert to PyTorch tensors
        X_tensor = torch.FloatTensor(X)
        y_tensors = {
            k: torch.LongTensor(v) for k, v in y_dict.items()
        }
        
        # Create data loaders
        dataset = TensorDataset(X_tensor, *y_tensors.values())
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )
        
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=self.batch_size)
        
        # Initialize model and optimizer
        model = self.predictor.model
        optimizer = torch.optim.AdamW(model.parameters(), lr=self.learning_rate, 
                                    weight_decay=0.01)
        
        # Learning rate scheduler
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=self.learning_rate,
            epochs=self.num_epochs,
            steps_per_epoch=len(train_loader)
        )
        
        # Loss function with label smoothing
        criterion = nn.CrossEntropyLoss(label_smoothing=self.label_smoothing)
        
        # Training loop
        best_val_loss = float('inf')
        for epoch in range(self.num_epochs):
            # Training phase
            model.train()
            train_losses = []
            for batch in train_loader:
                X_batch = batch[0]
                y_batch = batch[1:]
                
                optimizer.zero_grad()
                outputs = model(X_batch)
                
                # Calculate loss for each head
                loss = sum(criterion(output, target) 
                          for output, target in zip(outputs, y_batch))
                
                loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                
                optimizer.step()
                scheduler.step()
                
                train_losses.append(loss.item())
            
            # Validation phase
            model.eval()
            val_losses = []
            all_preds = {k: [] for k in y_dict.keys()}
            all_targets = {k: [] for k in y_dict.keys()}
            
            with torch.no_grad():
                for batch in val_loader:
                    X_batch = batch[0]
                    y_batch = batch[1:]
                    
                    outputs = model(X_batch)
                    loss = sum(criterion(output, target) 
                             for output, target in zip(outputs, y_batch))
                    val_losses.append(loss.item())
                    
                    # Store predictions and targets
                    for i, k in enumerate(y_dict.keys()):
                        all_preds[k].extend(outputs[i].argmax(1).cpu().numpy())
                        all_targets[k].extend(y_batch[i].cpu().numpy())
            
            # Calculate metrics
            metrics = self._calculate_style_metrics(all_targets, all_preds)
            metrics['train_loss'] = np.mean(train_losses)
            metrics['val_loss'] = np.mean(val_losses)
            metrics['learning_rate'] = scheduler.get_last_lr()[0]
            self.log_metrics(metrics, epoch)
            
            # Save best model
            if np.mean(val_losses) < best_val_loss:
                best_val_loss = np.mean(val_losses)
                self.save_model(model, 'style_model')
                
                # Generate and save confusion matrices
                self._save_confusion_matrices(all_targets, all_preds)
        
        return self.predictor
    
    def _calculate_style_metrics(self, targets: Dict[str, List], preds: Dict[str, List]) -> Dict[str, float]:
        """Calculate style-specific metrics
        
        Args:
            targets: True labels for each category
            preds: Predicted labels for each category
        Returns:
            Dictionary of metrics
        """
        metrics = {}
        for category in targets:
            category_metrics = self.evaluate(
                np.array(targets[category]),
                np.array(preds[category])
            )
            metrics.update({
                f'{category}_{k}': v 
                for k, v in category_metrics.items()
            })
        
        # Calculate macro average across categories
        metrics['macro_accuracy'] = np.mean([
            metrics[f'{cat}_accuracy'] for cat in targets
        ])
        
        return metrics
    
    def _save_confusion_matrices(self, targets: Dict[str, List], preds: Dict[str, List]):
        """Generate and save confusion matrices for each category
        
        Args:
            targets: True labels for each category
            preds: Predicted labels for each category
        """
        for category in targets:
            cm = confusion_matrix(targets[category], preds[category])
            labels = self.label_encoders[category].classes_
            
            plt.figure(figsize=(10, 8))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=labels, yticklabels=labels)
            plt.title(f'Confusion Matrix - {category}')
            plt.xlabel('Predicted')
            plt.ylabel('True')
            plt.tight_layout()
            
            # Save plot
            plt.savefig(self.model_dir / f'{category}_confusion_matrix.png')
            plt.close()
    
    def analyze_errors(self, X_val: np.ndarray, y_val: Dict[str, np.ndarray]) -> pd.DataFrame:
        """Analyze prediction errors
        
        Args:
            X_val: Validation features
            y_val: True labels for each category
        Returns:
            DataFrame with error analysis
        """
        model = self.predictor.model
        model.eval()
        
        with torch.no_grad():
            outputs = model(torch.FloatTensor(X_val))
        
        error_dfs = []
        for i, (category, y) in enumerate(y_val.items()):
            preds = outputs[i].argmax(1).cpu().numpy()
            probs = nn.Softmax(dim=1)(outputs[i]).max(1).values.cpu().numpy()
            
            # Decode labels
            true_labels = self.label_encoders[category].inverse_transform(y)
            pred_labels = self.label_encoders[category].inverse_transform(preds)
            
            df = pd.DataFrame({
                'category': category,
                'true_label': true_labels,
                'predicted_label': pred_labels,
                'confidence': probs,
                'error': true_labels != pred_labels
            })
            error_dfs.append(df[df['error']])
        
        return pd.concat(error_dfs).sort_values('confidence', ascending=False)