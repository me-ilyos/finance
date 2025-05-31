import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file_contacts': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'contacts.log'),
            'formatter': 'verbose',
        },
        'file_sales': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'sales.log'),
            'formatter': 'verbose',
        },
        'file_accounting': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'accounting.log'),
            'formatter': 'verbose',
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'errors.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'apps.contacts': {
            'handlers': ['file_contacts', 'file_errors', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.sales': {
            'handlers': ['file_sales', 'file_errors', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.accounting': {
            'handlers': ['file_accounting', 'file_errors', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['file_errors', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['file_errors', 'console'],
        'level': 'WARNING',
    },
}


def setup_logging():
    """Setup logging configuration"""
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Create initial log entries
    logger = logging.getLogger('apps.core')
    logger.info(f"Logging initialized at {datetime.now()}")
    logger.info(f"Log files directory: {os.path.abspath(LOG_DIR)}") 