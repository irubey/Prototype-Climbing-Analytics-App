import schedule
import time
import logging
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Optional
import os

from ..training.grade_trainer import GradeTrainer
from ..training.send_trainer import SendTrainer
from ..training.style_trainer import StyleTrainer
from ..data.data_quality import get_quality_training_data

class ModelTrainingScheduler:
    """Schedules and manages automated model training"""
    
    def __init__(self, 
                 models_dir: str = 'models',
                 training_frequency: str = 'weekly',
                 min_new_samples: int = 1000):
        """Initialize the training scheduler
        
        Args:
            models_dir: Directory for model storage
            training_frequency: How often to train ('daily', 'weekly', 'monthly')
            min_new_samples: Minimum new samples required for training
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.training_frequency = training_frequency
        self.min_new_samples = min_new_samples
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Setup logging
        logging.basicConfig(
            filename=self.models_dir / 'training.log',
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def setup_schedule(self):
        """Setup training schedule based on frequency"""
        if self.training_frequency == 'daily':
            schedule.every().day.at("02:00").do(self.train_all_models)
        elif self.training_frequency == 'weekly':
            schedule.every().monday.at("02:00").do(self.train_all_models)
        elif self.training_frequency == 'monthly':
            schedule.every().first_monday_of_month.at("02:00").do(self.train_all_models)
    
    def train_all_models(self) -> Dict[str, bool]:
        """Train all models if conditions are met
        
        Returns:
            Dictionary indicating success of each model's training
        """
        self.logger.info("Starting scheduled model training...")
        
        # Check if we have enough new data
        if not self._check_data_requirements():
            self.logger.info("Not enough new data for training")
            return {'status': 'skipped', 'reason': 'insufficient_data'}
        
        results = {}
        try:
            # Train grade model
            self.logger.info("Training grade model...")
            grade_trainer = GradeTrainer(model_dir=self.models_dir)
            grade_predictor = grade_trainer.train()
            results['grade_model'] = True
            
            # Train send model
            self.logger.info("Training send model...")
            send_trainer = SendTrainer(model_dir=self.models_dir)
            send_predictor = send_trainer.train()
            results['send_model'] = True
            
            # Train style model
            self.logger.info("Training style model...")
            style_trainer = StyleTrainer(model_dir=self.models_dir)
            style_predictor = style_trainer.train()
            results['style_model'] = True
            
            # Save training metadata
            self._save_training_metadata(results)
            
        except Exception as e:
            self.logger.error(f"Error during training: {str(e)}")
            results['error'] = str(e)
        
        return results
    
    def _check_data_requirements(self) -> bool:
        """Check if we have enough new data for training
        
        Returns:
            Boolean indicating if training should proceed
        """
        # Get last training metadata
        last_training = self._load_training_metadata()
        if not last_training:
            return True
        
        # Get current data count
        current_data = get_quality_training_data()
        current_count = len(current_data)
        
        # Check if we have enough new samples
        last_count = last_training.get('data_count', 0)
        new_samples = current_count - last_count
        
        self.logger.info(f"New samples since last training: {new_samples}")
        return new_samples >= self.min_new_samples
    
    def _save_training_metadata(self, results: Dict) -> None:
        """Save metadata about training run
        
        Args:
            results: Dictionary of training results
        """
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'data_count': len(get_quality_training_data()),
            'training_frequency': self.training_frequency,
            'min_new_samples': self.min_new_samples
        }
        
        metadata_path = self.models_dir / 'training_metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_training_metadata(self) -> Optional[Dict]:
        """Load metadata from last training run
        
        Returns:
            Dictionary of metadata or None if no previous training
        """
        metadata_path = self.models_dir / 'training_metadata.json'
        if not metadata_path.exists():
            return None
            
        with open(metadata_path, 'r') as f:
            return json.load(f)
    
    def run(self):
        """Run the scheduler"""
        self.setup_schedule()
        
        self.logger.info(f"Starting scheduler with {self.training_frequency} frequency")
        while True:
            schedule.run_pending()
            time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    scheduler = ModelTrainingScheduler(
        training_frequency='weekly',
        min_new_samples=1000
    )
    scheduler.run()
