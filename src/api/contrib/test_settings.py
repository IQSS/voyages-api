"""Isolated settings for contribution contract and transaction tests."""
import os

SECRET_KEY = 'contribution-tests-only'
CONTRIB_SERVICE_TOKEN = 'contribution-service-tests-only'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes',
    'rest_framework', 'rest_framework.authtoken',
    'common', 'geo', 'voyage', 'past', 'document', 'contrib',
]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.environ.get('CONTRIB_TEST_DB_PORT'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.mysql', 'HOST': os.environ.get('CONTRIB_TEST_DB_HOST', '127.0.0.1'),
        'PORT': os.environ['CONTRIB_TEST_DB_PORT'], 'NAME': 'contrib_tests',
        'USER': 'root', 'PASSWORD': os.environ['CONTRIB_TEST_DB_PASSWORD'],
        'OPTIONS': {'charset': 'utf8mb4'},
    }
ROOT_URLCONF = 'contrib.test_urls'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
}
MIDDLEWARE = []
ALLOWED_HOSTS = ['testserver']
