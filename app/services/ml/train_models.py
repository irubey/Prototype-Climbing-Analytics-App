import logging
from pathlib import Path
import sys
import gc
import torch
import os

from app import app
from app.services.ml.training.grade_trainer import GradeTrainer
from app.services.ml.training.style_trainer import StyleTrainer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_gpu():
    """Configure GPU settings for optimal training"""
    if torch.cuda.is_available():
        # Enable cuDNN autotuner
        torch.backends.cudnn.benchmark = True
        
        # Set memory growth
        for device in range(torch.cuda.device_count()):
            torch.cuda.set_per_process_memory_fraction(0.9, device)
        
        # Log GPU info
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"Using GPU: {gpu_name} with {gpu_memory:.1f}GB memory")
        
        # Set environment variables for better GPU utilization
        os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Reduce TensorFlow logging
        
        return True
    return False

def clear_memory():
    """Aggressively clear GPU and CPU memory"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        # Force garbage collection
        for obj in gc.get_objects():
            if torch.is_tensor(obj):
                obj.cpu()

def main():
    try:
        # Initialize GPU settings
        using_gpu = setup_gpu()
        
        # Use the Flask app context
        with app.app_context():
            # Train grade predictor
            logger.info("Training grade predictor...")
            grade_trainer = GradeTrainer()
            grade_predictor = grade_trainer.train()
            clear_memory()
            
            # Train style predictor
            logger.info("Training style predictor...")
            style_trainer = StyleTrainer()
            style_predictor = style_trainer.train()
            clear_memory()
            
            logger.info("All models trained successfully!")

    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        clear_memory()  # Clean up on error
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Failed to initialize app context: {str(e)}")
        raise 