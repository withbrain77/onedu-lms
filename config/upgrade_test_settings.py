"""Disposable upgrade rehearsal; production connection variables are ignored."""
import os
from urllib.parse import urlparse

import dj_database_url

from .browser_test_settings import *  # noqa: F403

UPGRADE_ROOT = BASE_DIR / '.qa' / 'upgrade' / 'rehearsal'
UPGRADE_ROOT.mkdir(parents=True, exist_ok=True)
database_url = os.environ.get('UPGRADE_TEST_DATABASE_URL', '')
if database_url:
    parsed = urlparse(database_url)
    if parsed.hostname not in ('localhost', '127.0.0.1') or parsed.path != '/onedu_upgrade':
        raise ValueError('Upgrade rehearsal requires a local database named onedu_upgrade.')
    DATABASES = {'default': dj_database_url.parse(database_url)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': UPGRADE_ROOT / 'db.sqlite3'}}
MEDIA_ROOT = UPGRADE_ROOT / 'media'
PRIVATE_MEDIA_ROOT = UPGRADE_ROOT / 'private'
STATIC_ROOT = UPGRADE_ROOT / 'static'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
USE_X_ACCEL_REDIRECT = False

