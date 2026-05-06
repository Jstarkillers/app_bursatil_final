import os
import logging
import logging.handlers
from dotenv import load_dotenv

# Load .env from the project root (parent of backend/)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# ============================================
# PostgreSQL Configuration
# ============================================
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'comerciotech')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

# ============================================
# MongoDB Configuration
# ============================================
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', 27017))
MONGODB_DB = os.getenv('MONGODB_DB', 'comerciotech')
MONGODB_URI = os.getenv('MONGODB_URI', f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/')

# ============================================
# Flask Configuration
# ============================================
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# ============================================
# Negocio
# ============================================
INITIAL_BALANCE = int(os.getenv('INITIAL_BALANCE', 10_000_000))  # CLP
SYNC_INTERVAL_MINUTES = int(os.getenv('SYNC_INTERVAL_MINUTES', 30))
TRANSACTION_LIMIT_DEFAULT = int(os.getenv('TRANSACTION_LIMIT_DEFAULT', 50))

# ============================================
# API Bolsa de Santiago
# ============================================
BOLSA_API_KEY = os.getenv('BOLSA_API_KEY', '')
BOLSA_API_BASE_URL = os.getenv(
    'BOLSA_API_BASE_URL',
    'https://api-private-braindata.bolsadesantiago.com/api-servicios-de-consulta/api/Util'
)

# ============================================
# Logging
# ============================================
LOG_DIR = os.getenv('LOG_DIR', os.path.join(os.path.dirname(__file__), '..', 'logs'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')


def setup_logging():
    """Configura logging con salida a consola y archivo rotativo."""
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Archivo rotativo (10 MB × 5 archivos)
    log_file = os.path.join(LOG_DIR, 'nexobolsa.log')
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
