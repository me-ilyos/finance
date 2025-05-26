from .base import *

# Override or add settings for local development here
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Example: Add django-debug-toolbar for local development
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
# INTERNAL_IPS = ['127.0.0.1'] 