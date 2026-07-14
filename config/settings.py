"""
Django settings for the approval-based LMS MVP.
"""

import os
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or value == '':
        return default
    return int(value)


def env_list(*names):
    for name in names:
        raw_value = os.getenv(name)
        if raw_value:
            return [item.strip() for item in raw_value.split(',') if item.strip()]
    return []


def env_path(name, default):
    return Path(os.getenv(name, str(default)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

DEBUG = env_bool('DJANGO_DEBUG', True)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY and DEBUG:
    SECRET_KEY = 'django-insecure-local-mvp-change-me-before-production'
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=False.')

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'ALLOWED_HOSTS')
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', 'CSRF_TRUSTED_ORIGINS')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'courses',
    'lessons',
    'enrollments',
    'progress',
    'quizzes',
    'certificates',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.onedu_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env_int('DB_CONN_MAX_AGE', 600),
            ssl_require=env_bool('DB_SSL_REQUIRE', False),
        )
    }
elif os.getenv('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB'),
            'USER': os.getenv('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', 'db'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': env_int('DB_CONN_MAX_AGE', 600),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': env_path('SQLITE_PATH', BASE_DIR / 'db.sqlite3'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = os.getenv('STATIC_URL', 'static/')
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = env_path('STATIC_ROOT', BASE_DIR / 'staticfiles')

MEDIA_URL = os.getenv('MEDIA_URL', 'media/')
MEDIA_ROOT = env_path('MEDIA_ROOT', BASE_DIR / 'media')
PRIVATE_MEDIA_ROOT = env_path('PRIVATE_MEDIA_ROOT', BASE_DIR / 'private_media')
CERTIFICATE_ISSUER_NAME = os.getenv('CERTIFICATE_ISSUER_NAME', 'Onedu LMS')
CERTIFICATE_FONT_PATH = os.getenv('CERTIFICATE_FONT_PATH', '')
USE_X_ACCEL_REDIRECT = env_bool('USE_X_ACCEL_REDIRECT', False)
X_ACCEL_REDIRECT_PREFIX = os.getenv('X_ACCEL_REDIRECT_PREFIX', '/protected-media/')
PUBLIC_SITE_URL = os.getenv('DJANGO_PUBLIC_SITE_URL', '').strip().rstrip('/')

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_TASK_ALWAYS_EAGER = env_bool('CELERY_TASK_ALWAYS_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = env_bool('CELERY_TASK_EAGER_PROPAGATES', True)
CELERY_TASK_DEFAULT_QUEUE = os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'default')
CELERY_VIDEO_QUEUE = os.getenv('CELERY_VIDEO_QUEUE', 'video')
CELERY_TIMEZONE = TIME_ZONE
CELERY_EXPIRY_NOTICE_HOUR = env_int('CELERY_EXPIRY_NOTICE_HOUR', 9)
CELERY_EXPIRY_NOTICE_MINUTE = env_int('CELERY_EXPIRY_NOTICE_MINUTE', 0)
CELERY_TASK_ROUTES = {
    'lessons.tasks.convert_lesson_hls_task': {'queue': CELERY_VIDEO_QUEUE},
    'enrollments.tasks.send_expiry_notices_task': {'queue': CELERY_TASK_DEFAULT_QUEUE},
}
CELERY_BEAT_SCHEDULE = {
    'send-enrollment-expiry-notices-daily': {
        'task': 'enrollments.tasks.send_expiry_notices_task',
        'schedule': crontab(hour=CELERY_EXPIRY_NOTICE_HOUR, minute=CELERY_EXPIRY_NOTICE_MINUTE),
        'options': {'queue': CELERY_TASK_DEFAULT_QUEUE},
    },
}

DEFAULT_FROM_EMAIL = os.getenv('DJANGO_DEFAULT_FROM_EMAIL', 'Onedu LMS <no-reply@example.com>')
SERVER_EMAIL = os.getenv('DJANGO_SERVER_EMAIL', DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.getenv(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('DJANGO_EMAIL_HOST', 'localhost')
EMAIL_PORT = env_int('DJANGO_EMAIL_PORT', 25)
EMAIL_HOST_USER = os.getenv('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('DJANGO_EMAIL_USE_TLS', False)
EMAIL_USE_SSL = env_bool('DJANGO_EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = env_int('DJANGO_EMAIL_TIMEOUT', 10)
ONEDU_NOTIFY_ENROLLMENT_REQUEST = env_bool('ONEDU_NOTIFY_ENROLLMENT_REQUEST', True)
ONEDU_NOTIFY_ENROLLMENT_APPROVAL = env_bool('ONEDU_NOTIFY_ENROLLMENT_APPROVAL', True)
ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D = env_bool('ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D', True)
ONEDU_ADMIN_NOTIFICATION_EMAILS = env_list(
    'ONEDU_ADMIN_NOTIFICATION_EMAILS',
    'ONEDU_ADMIN_NOTIFICATION_EMAIL',
)
if not ONEDU_ADMIN_NOTIFICATION_EMAILS and EMAIL_HOST_USER:
    ONEDU_ADMIN_NOTIFICATION_EMAILS = [EMAIL_HOST_USER]
ONEDU_DEPOSIT_NOTICE = {
    'bank': os.getenv('ONEDU_DEPOSIT_BANK', '국민은행'),
    'account': os.getenv('ONEDU_DEPOSIT_ACCOUNT', '700101-01-323177'),
    'holder': os.getenv('ONEDU_DEPOSIT_HOLDER', '표진호(위드브레인)'),
    'payer_note': os.getenv('ONEDU_DEPOSIT_PAYER_NOTE', '수강생 이름과 동일하게 입력해 주세요.'),
}
ONEDU_ACCESS_LOG_ENABLED = env_bool('ONEDU_ACCESS_LOG_ENABLED', True)
ONEDU_ACCESS_LOG_CONCURRENCY_WINDOW_MINUTES = env_int('ONEDU_ACCESS_LOG_CONCURRENCY_WINDOW_MINUTES', 15)

SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', not DEBUG)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = env_bool('DJANGO_USE_X_FORWARDED_HOST', False)
SECURE_HSTS_SECONDS = env_int('DJANGO_SECURE_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'enrollments:classroom'
LOGOUT_REDIRECT_URL = 'courses:list'

MESSAGE_TAGS = {
    messages.ERROR: 'danger',
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
