import logging
from pathlib import Path
import sys
import gc
import torch

from app import app  # Import the Flask app instance directly
from app.services.ml.training.grade_trainer import GradeTrainer
from app.services.ml.training.style_trainer import StyleTrainer
from app.services.ml.training.send_trainer import SendTrainer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Use the Flask app context
        with app.app_context():
            try:
                # Train grade predictor
                logger.info("Training grade predictor...")
                grade_trainer = GradeTrainer()
                grade_predictor = grade_trainer.train()
                
                # Clear memory before next model
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Train send predictor
                logger.info("Training send predictor...")
                send_trainer = SendTrainer()
                send_predictor = send_trainer.train()
                
                # Clear memory before next model
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Train style predictor
                logger.info("Training style predictor...")
                style_trainer = StyleTrainer()
                style_predictor = style_trainer.train()
                
            except Exception as e:
                logger.error(f"Training failed: {str(e)}")
                raise
    except Exception as e:
        logger.error(f"Failed to initialize app context: {str(e)}")
        raise

if __name__ == "__main__":
    main() 