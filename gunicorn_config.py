import multiprocessing
import os

# Server socket settings
bind = "0.0.0.0:" + os.getenv("PORT", "10000")
backlog = 512

# Worker processes - optimized for free tier
workers = 1
worker_class = 'gthread'
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_connections = 100
timeout = 25
graceful_timeout = 20
keepalive = 2

# Process naming
proc_name = 'climbapp'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Memory management - aggressive settings for free tier
max_requests = 500
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

# Limits - reduced for free tier
limit_request_line = 2048
limit_request_fields = 50
limit_request_field_size = 4096

def post_fork(server, worker):
    """Set process name and configure worker memory limits"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # Set memory limit if specified - reduced for free tier
    memory_limit = int(os.getenv("PYTHON_MEMORY_LIMIT", "450")) * 1024 * 1024  # Convert MB to bytes
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        
        # Enable garbage collection
        import gc
        gc.enable()
        gc.set_threshold(100, 5, 5)  # More aggressive GC
    except (ImportError, ValueError):
        pass 