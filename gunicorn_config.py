import multiprocessing
import os

# Server socket settings
bind = "0.0.0.0:" + os.getenv("PORT", "10000")
backlog = 256

# Worker processes - optimized for free tier
workers = 1
worker_class = 'sync'
threads = 1
worker_connections = 50
timeout = 25
graceful_timeout = 20
keepalive = 2

# Process naming
proc_name = 'climbapp'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Memory management - more aggressive settings
max_requests = 250
max_requests_jitter = 25
worker_tmp_dir = '/dev/shm'

# Process management
preload_app = True
reload = False

# Debug config
spew = False
check_config = False

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Limits - reduced further
limit_request_line = 1024
limit_request_fields = 25
limit_request_field_size = 2048

def post_fork(server, worker):
    """Set process name and configure worker memory limits"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # Set memory limit if specified - reduced further
    memory_limit = int(os.getenv("PYTHON_MEMORY_LIMIT", "400")) * 1024 * 1024  # Reduced to 400MB
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        
        # More aggressive garbage collection
        import gc
        gc.enable()
        gc.set_threshold(50, 3, 3)  # Even more aggressive GC
        
        # Disable unnecessary features
        import sys
        sys.dont_write_bytecode = True  # Prevent writing .pyc files
    except (ImportError, ValueError):
        pass 