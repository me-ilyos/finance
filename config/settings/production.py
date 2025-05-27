from .base import *

DEBUG = False

ALLOWED_HOSTS = ['your_domain.com', 'www.your_domain.com']

# Example: Configure a different database for production
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'your_prod_db_name',
#         'USER': 'your_prod_db_user',
#         'PASSWORD': 'your_prod_db_password',
#         'HOST': 'your_prod_db_host',
#         'PORT': 'your_prod_db_port',
#     }
# }

# Example: Configure static files for production (e.g., using WhiteNoise or a CDN)
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage' 