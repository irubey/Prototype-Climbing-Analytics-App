import multiprocessing
import os

# Server socket settings
bind = "0.0.0.0:" + os.getenv("PORT", "10000")
backlog = 1024

# Worker processes - use environment variables
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
worker_class = 'gthread'
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_connections = 250
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = timeout
keepalive = 5

# Process naming
proc_name = 'climbapp'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Memory management
max_requests = 1000
max_requests_jitter = 50
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

# Limits
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

def post_fork(server, worker):
    """Set process name and configure worker memory limits"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # Set memory limit if specified
    memory_limit = int(os.getenv("PYTHON_MEMORY_LIMIT", "512")) * 1024 * 1024  # Convert MB to bytes
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    except (ImportError, ValueError):
        pass 