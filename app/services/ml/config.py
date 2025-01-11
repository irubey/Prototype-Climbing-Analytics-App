import os
import torch
import gc

def clear_gpu_cache():
    """Clear GPU cache and garbage collect"""
    if torch.cuda.is_available():
        # Clear CUDA cache
        torch.cuda.empty_cache()
        # Reset peak memory stats
        torch.cuda.reset_peak_memory_stats()
    # Force garbage collection
    gc.collect()

def configure_hardware():
    """Configure hardware optimizations for ML operations"""
    
    # Clear any existing cache first
    clear_gpu_cache()
    
    # CPU Optimizations
    NUM_CORES = 6  # i5-10600K has 6 cores
    
    # Intel MKL Settings
    os.environ["MKL_NUM_THREADS"] = str(NUM_CORES)
    os.environ["NUMEXPR_NUM_THREADS"] = str(NUM_CORES)
    os.environ["OMP_NUM_THREADS"] = str(NUM_CORES)
    os.environ["OPENBLAS_NUM_THREADS"] = str(NUM_CORES)
    os.environ["VECLIB_MAXIMUM_THREADS"] = str(NUM_CORES)
    
    # Memory optimizations
    os.environ["MALLOC_CONF"] = "oversize_threshold:1,background_thread:true,metadata_thp:auto,dirty_decay_ms:9000000000,muzzy_decay_ms:9000000000"
    
    # Configure PyTorch
    if torch.cuda.is_available():
        # GPU settings
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        # Set default tensor type to CUDA
        torch.set_default_tensor_type('torch.cuda.FloatTensor')
        # Print GPU memory usage
        print(f"GPU Memory Usage:")
        print(f"Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f}MB")
        print(f"Cached: {torch.cuda.memory_reserved(0) / 1024**2:.2f}MB")
    else:
        # CPU settings for PyTorch
        torch.set_num_threads(NUM_CORES)
        torch.set_num_interop_threads(2)

def get_device():
    """Get the optimal device for ML operations"""
    if torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu') 