# Gunicorn configuration — NEXO BOLSA
# Usar con: gunicorn -c gunicorn.conf.py app:app

import multiprocessing
import os

# Workers: 2 × CPU cores + 1 (recomendado para I/O bound)
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
threads = 2

# Red
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:5000')
timeout = 60
keepalive = 5

# Logs
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '/var/log/nexobolsa/access.log')
errorlog  = os.getenv('GUNICORN_ERROR_LOG',  '/var/log/nexobolsa/error.log')
loglevel  = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# Seguridad
limit_request_line   = 4096
limit_request_fields = 100

# Graceful restart
graceful_timeout = 30
