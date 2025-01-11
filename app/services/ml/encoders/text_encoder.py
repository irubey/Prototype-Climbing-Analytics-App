import torch
from transformers import RobertaModel, RobertaTokenizer
import numpy as np
from typing import List, Dict
import gc

class ClimbingNoteEncoder:
    def __init__(self, max_length=128, device='cpu'):
        """Initialize the climbing-specific text encoder
        
        Args:
            max_length: Maximum sequence length
            device: Device to run model on ('cpu' or 'cuda')
        """
        self.max_length = max_length
        self.device = device if torch.cuda.is_available() else 'cpu'
        
        # Load model and tokenizer
        self.tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
        self.encoder = RobertaModel.from_pretrained('roberta-base').to(self.device)
        self.encoder.eval()  # Set to evaluation mode
        
        # Keep our comprehensive climbing terms for quality analysis
        self.climbing_terms = {
            # Movement Descriptors
            'beta': 1.5,
            'sequence': 1.4,
            'dyno': 1.4,
            
            # Technical Sections
            'crux': 1.3,
            'traverse': 1.3,
            
            # Hold Types
            'crimp': 1.2,
            'sloper': 1.2,
            'pinch': 1.2,
            
            # Basic Descriptors
            'hold': 1.1,
            'move': 1.1
        }
    
    def preprocess_text(self, text: str) -> str:
        """Clean and standardize climbing notes"""
        if not isinstance(text, str):
            return ""
            
        text = text.lower().strip()
        
        # Standardize common abbreviations
        replacements = {
            'proj': 'project',
            'os': 'onsight',
            'fl': 'flash',
            'rp': 'redpoint',
            'pp': 'pinkpoint'
        }
        
        for old, new in replacements.items():
            text = text.replace(f' {old} ', f' {new} ')
        
        return text
    
    def encode_batch(self, texts: List[str], batch_size: int = 8) -> np.ndarray:
        """Encode a batch of texts using RoBERTa
        
        Args:
            texts: List of texts to encode
            batch_size: Size of mini-batches for memory efficiency
        Returns:
            numpy array of encodings
        """
        encodings = []
        
        # Process in mini-batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_texts = [self.preprocess_text(text) for text in batch_texts]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors='pt'
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get embeddings
            with torch.no_grad():
                outputs = self.encoder(**inputs)
                # Use CLS token embedding
                batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            
            encodings.append(batch_embeddings)
            
            # Clear memory
            del inputs, outputs
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
            gc.collect()
        
        return np.vstack(encodings)
    
    def clear_cache(self):
        """Clear GPU and CPU memory caches"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
    
    def __del__(self):
        """Cleanup when object is deleted"""
        self.clear_cache()