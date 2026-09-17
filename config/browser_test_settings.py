"""Isolated browser checks. Never use production databases, media or mail."""
from .settings import *  # noqa: F403

DEBUG = True
SECRET_KEY = 'isolated-browser-tests-only'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / '.browser-tests/db.sqlite3'}}
MEDIA_ROOT = BASE_DIR / '.browser-tests/media'
PRIVATE_MEDIA_ROOT = BASE_DIR / '.browser-tests/private'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ONEDU_EMAIL_ASYNC = False
ONEDU_NOTIFY_ENROLLMENT_REQUEST = False
ONEDU_NOTIFY_ENROLLMENT_APPROVAL = False
ONEDU_NOTIFY_ACCOUNT_WITHDRAWAL_REQUEST = False
ONEDU_AUTOMATED_BACKUP_ENABLED = False
ONEDU_PUBLIC_IP_CHECK_URL = ''
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
