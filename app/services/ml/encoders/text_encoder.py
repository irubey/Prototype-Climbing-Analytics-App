import torch
from transformers import RobertaModel, RobertaTokenizer
import numpy as np
from typing import List, Dict
import gc
from ..config import get_device, clear_gpu_cache

class ClimbingNoteEncoder:
    def __init__(self, max_length=128):
        """Initialize the climbing-specific text encoder
        
        Args:
            max_length: Maximum sequence length
        """
        # Clear any existing cache
        clear_gpu_cache()
        
        self.max_length = max_length
        self.device = get_device()
        
        # Load model and tokenizer with optimizations
        self.tokenizer = RobertaTokenizer.from_pretrained('roberta-base', use_fast=True)
        self.encoder = RobertaModel.from_pretrained(
            'roberta-base',
            torchscript=False,  # Disable TorchScript
            return_dict=True  # Return dictionary outputs
        ).to(self.device)
        
        # Set to evaluation mode and enable memory efficient optimizations
        self.encoder.eval()
        if torch.cuda.is_available():
            # Enable automatic mixed precision
            self.encoder = self.encoder.half()  # Convert to FP16
            torch.backends.cudnn.benchmark = True
            # Set memory efficient attention
            self.encoder.config.use_cache = False
        
        # Pre-compile forward pass for common batch sizes
        self._warmup()
        
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
    
    def _warmup(self):
        """Warmup the model with dummy inputs for common batch sizes"""
        if torch.cuda.is_available():
            # Clear cache before warmup
            clear_gpu_cache()
            
            # Warmup with different batch sizes
            for batch_size in [1, 4, 8, 16]:
                dummy_input = self.tokenizer(
                    ["dummy text"] * batch_size,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors='pt'
                ).to(self.device)
                
                with torch.amp.autocast(device_type='cuda'), torch.no_grad():
                    _ = self.encoder(**dummy_input)
            
            # Clear cache after warmup
            clear_gpu_cache()
    
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
    
    @torch.no_grad()  # Disable gradient computation
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Encode a batch of texts using the RoBERTa model
        
        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding
            
        Returns:
            Array of encoded text embeddings
        """
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.encoder = self.encoder.to(device)
        
        # Initialize list to store embeddings
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            
            # Move inputs to device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Get embeddings
            with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                with torch.no_grad():
                    outputs = self.encoder(**inputs)
                    # Get CLS token embedding from the dictionary output
                    embeddings = outputs.last_hidden_state[:, 0, :].float()
                    # Move to CPU and convert to numpy
                    embeddings = embeddings.cpu().numpy()
                    all_embeddings.append(embeddings)
        
        # Concatenate all batches
        return np.vstack(all_embeddings)
    
    def clear_cache(self):
        """Clear GPU and CPU memory caches"""
        clear_gpu_cache()
    
    def __del__(self):
        """Cleanup when object is deleted"""
        self.clear_cache()
    
    def get_climbing_term_importance(self, note: str) -> Dict[str, float]:
        """Analyze importance of climbing terms in a note
        
        Args:
            note: Climbing note text
        Returns:
            Dict mapping climbing terms to their importance scores
        """
        # Common climbing terms and their base importance
        climbing_terms = {
            'crux': 1.0,
            'beta': 0.9,
            'hold': 0.8,
            'crimp': 0.9,
            'jug': 0.8,
            'pinch': 0.8,
            'sloper': 0.9,
            'dyno': 0.9,
            'sequence': 0.8,
            'protection': 0.7,
            'anchor': 0.7,
            'pitch': 0.8,
            'belay': 0.7,
            'roof': 0.8,
            'overhang': 0.8,
            'slab': 0.8,
            'crack': 0.8,
            'trad': 0.7,
            'sport': 0.7,
            'boulder': 0.7,
            'onsight': 0.6,
            'flash': 0.6,
            'redpoint': 0.6,
            'project': 0.6
        }
        
        # Find terms in note and calculate importance
        found_terms = {}
        note_lower = note.lower()
        
        for term, base_importance in climbing_terms.items():
            if term in note_lower:
                # Increase importance if term appears multiple times
                count = note_lower.count(term)
                importance = min(base_importance * (1 + 0.2 * (count - 1)), 1.0)
                found_terms[term] = importance
                
        return found_terms