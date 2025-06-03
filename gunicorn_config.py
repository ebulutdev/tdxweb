import multiprocessing
import os

# Server socket
port = int(os.environ.get("PORT", 10000))
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
workers = 1  # Use only 1 worker to reduce memory usage
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Increase timeout to handle slow requests
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'stockdb'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None

# Health check
graceful_timeout = 120
preload_app = True 