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
    
    # Define style categories as class attributes
    STYLE_CATEGORIES = ['discipline', 'lead_style', 'length_category']
    
    def __init__(self, batch_size: int = 128, num_epochs: int = 20, 
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
        
        # Initialize style categories and label encoders
        self.style_categories = self.STYLE_CATEGORIES
        self.label_encoders = {
            category: LabelEncoder() for category in self.style_categories
        }
        
        # Enable cuDNN benchmarking and deterministic mode
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = True
        
        # Import db directly from app module
        from app import db
        self.db = db
    
    def load_data(self) -> pd.DataFrame:
        """Load high-quality training data"""
        df = get_quality_training_data()
        
        # Log data info
        logging.info(f"Loaded {len(df)} training examples")
        logging.info(f"Available columns: {df.columns.tolist()}")
        
        # Verify required columns
        required_columns = ['notes'] + self.style_categories
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
            
        return df
    
    def _prepare_labels(self, df: pd.DataFrame) -> Dict[str, torch.Tensor]:
        """Prepare labels for training by encoding categorical variables
        
        Args:
            df: DataFrame containing style labels
            
        Returns:
            Dictionary mapping category names to encoded label tensors
        """
        # Create copy to avoid modifying original
        filled_df = df.copy()
        encoded_labels = {}
        
        # Fill missing values with 'unknown' for each category
        for category in self.style_categories:
            # Log unique values before processing, handling None values
            unique_vals = df[category].unique()
            unique_before = sorted([str(x) for x in unique_vals if pd.notna(x)])
            logging.info(f"Unique {category} values before processing: {unique_before}")
            
            # Convert values to strings and handle missing values
            filled_df[category] = filled_df[category].fillna('unknown')
            filled_df[category] = filled_df[category].astype(str)
            
            # Get unique values including 'unknown'
            unique_values = pd.concat([
                pd.Series(filled_df[category].unique()),
                pd.Series(['unknown'])
            ]).drop_duplicates()
            
            # Log unique values after processing
            logging.info(f"Unique {category} values after processing: {sorted(unique_values)}")
            
            # Fit encoder on unique values
            self.label_encoders[category].fit(unique_values)
            
            # Transform values and ensure they're within bounds
            encoded = self.label_encoders[category].transform(filled_df[category].values)
            n_classes = len(self.label_encoders[category].classes_)
            
            # Log mapping between classes and indices
            class_mapping = dict(zip(self.label_encoders[category].classes_, range(n_classes)))
            logging.info(f"{category} class mapping: {class_mapping}")
            
            # Validate and clip labels
            encoded = np.clip(encoded, 0, n_classes - 1)
            encoded = encoded.astype(np.int64)
            
            # Convert to tensor
            encoded_labels[category] = torch.tensor(encoded, dtype=torch.int64)
            
            # Log category info
            logging.info(f"Category {category} has {n_classes} classes")
            logging.info(f"Label range: [{encoded_labels[category].min()}, {encoded_labels[category].max()}]")
            logging.info(f"Label dtype: {encoded_labels[category].dtype}")
            logging.info(f"Value counts: {pd.Series(encoded).value_counts().to_dict()}")
            
            # Double check tensor values
            assert torch.all(encoded_labels[category] >= 0), f"Found negative labels in {category}"
            assert torch.all(encoded_labels[category] < n_classes), f"Found labels >= {n_classes} in {category}"
        
        return encoded_labels
    
    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Prepare data for training
        
        Args:
            df: DataFrame with notes and style labels
            
        Returns:
            Tuple of (encoded notes, encoded style labels dict)
        """
        # Encode notes - ensure all notes are strings
        notes = df['notes'].fillna('').astype(str).tolist()
        logging.info(f"Encoding {len(notes)} notes for style prediction")
        X = self.predictor.text_encoder.encode_batch(notes)
        
        # Encode style labels
        y_dict = self._prepare_labels(df)
        
        # Log shape information
        logging.info(f"Encoded features shape: {X.shape}")
        for category, labels in y_dict.items():
            logging.info(f"{category} labels shape: {labels.shape}")
            
        return X, y_dict
    
    def train(self) -> StylePredictor:
        """Train style prediction model with GPU optimizations
        
        Returns:
            Trained StylePredictor
        """
        # Load and prepare data
        df = self.load_data()
        X, y_dict = self.prepare_data(df)
        
        # Convert to PyTorch tensors and move to GPU if available
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        X_tensor = torch.FloatTensor(X)
        y_tensors = {
            k: v.to(device) for k, v in y_dict.items()
        }
        
        # Create data loaders with pin memory for faster GPU transfer
        dataset = TensorDataset(X_tensor.cpu(), *[t.cpu() for t in y_dict.values()])
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )
        
        train_loader = DataLoader(
            train_dataset, 
            batch_size=self.batch_size, 
            shuffle=True,
            pin_memory=True,
            num_workers=3,
            persistent_workers=True
        )
        val_loader = DataLoader(
            val_dataset, 
            batch_size=self.batch_size,
            pin_memory=True,
            num_workers=3,
            persistent_workers=True
        )
        
        # Initialize model and move to GPU
        model = self.predictor.model.to(device)
        model.train()  # Ensure model is in training mode
        
        # Use AdamW with weight decay
        optimizer = torch.optim.AdamW(
            model.parameters(), 
            lr=self.learning_rate,
            weight_decay=0.01,
            betas=(0.9, 0.999)
        )
        
        # Learning rate scheduler with warmup
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=self.learning_rate,
            epochs=self.num_epochs,
            steps_per_epoch=len(train_loader),
            pct_start=0.1  # 10% warmup
        )
        
        # Loss function with label smoothing
        criterion = nn.CrossEntropyLoss(label_smoothing=self.label_smoothing)
        
        # Initialize mixed precision training
        scaler = torch.amp.GradScaler()
        
        # Training loop
        best_val_loss = float('inf')
        for epoch in range(self.num_epochs):
            # Training phase
            model.train()
            train_losses = []
            
            for batch in train_loader:
                # Move batch to GPU
                X = batch[0].to(device)
                y_dict = {
                    category: batch[i+1].to(device)
                    for i, category in enumerate(self.style_categories)
                }
                
                optimizer.zero_grad(set_to_none=True)  # More efficient than zero_grad()
                
                # Use automatic mixed precision
                with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                    outputs = model(X)
                    loss = sum(
                        criterion(outputs[category], y_dict[category])
                        for category in self.style_categories
                    )
                
                # Scale loss and compute gradients
                scaler.scale(loss).backward()
                
                # Update weights with gradient clipping
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
                
                # Step the learning rate scheduler after optimizer
                scheduler.step()
                
                train_losses.append(loss.item())
            
            # Validation phase
            model.eval()
            val_losses = []
            all_preds = {k: [] for k in self.style_categories}
            all_targets = {k: [] for k in self.style_categories}
            
            with torch.no_grad():
                for batch in val_loader:
                    X_val = batch[0].to(device)
                    y_val = {
                        category: batch[i+1].to(device)
                        for i, category in enumerate(self.style_categories)
                    }
                    
                    with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                        outputs = model(X_val)
                        loss = sum(
                            criterion(outputs[category], y_val[category])
                            for category in self.style_categories
                        )
                    val_losses.append(loss.item())
                    
                    # Store predictions and targets
                    for category in self.style_categories:
                        preds = outputs[category].argmax(1).cpu()
                        targets = y_val[category].cpu()
                        all_preds[category].extend(preds.numpy())
                        all_targets[category].extend(targets.numpy())
            
            # Calculate metrics
            metrics = self._calculate_style_metrics(all_targets, all_preds)
            metrics['train_loss'] = np.mean(train_losses)
            metrics['val_loss'] = np.mean(val_losses)
            metrics['learning_rate'] = scheduler.get_last_lr()[0]
            self.log_metrics(metrics, epoch)
            
            # Save best model
            if np.mean(val_losses) < best_val_loss:
                best_val_loss = np.mean(val_losses)
                model.cpu()  # Move to CPU for saving
                
                # Save model config and state
                model_config = {
                    'input_size': model.input_size,
                    'hidden_size': model.hidden_size,
                    'num_disciplines': model.num_disciplines,
                    'num_lead_styles': model.num_lead_styles,
                    'num_length_categories': model.num_length_categories
                }
                
                save_path = self.model_dir / 'style_model.pt'
                torch.save({
                    'model_config': model_config,
                    'model_state_dict': model.state_dict()
                }, save_path, _use_new_zipfile_serialization=True)
                
                self.logger.info(f"Model saved to {save_path}")
                model.to(device)  # Move back to GPU
                
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