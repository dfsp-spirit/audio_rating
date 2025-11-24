# gunicorn_conf.py -- Example production configuration for Gunicorn with Uvicorn workers
#
# To run the server with this configuration, use the command:
#
#     gunicorn -c /path/to/app/gunicorn_conf.py audiorating_backend.api:app
#

import multiprocessing

# Socket binding
bind = "127.0.0.1:8000"

# Worker processes
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 120
keepalive = 5

# Worker recycling (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "audiorating_backend"