#!/bin/sh
set -e

APP_USER="${ONEDU_APP_USER:-onedu}"
APP_GROUP="${ONEDU_APP_GROUP:-onedu}"
STATIC_DIR="${STATIC_ROOT:-/vol/web/static}"
MEDIA_DIR="${MEDIA_ROOT:-/vol/web/media}"
PRIVATE_MEDIA_DIR="${PRIVATE_MEDIA_ROOT:-/vol/web/private_media}"
LOG_DIR="${ONEDU_LOG_DIR:-/vol/web/logs}"
BACKUP_DIR="${ONEDU_BACKUP_ROOT:-/vol/web/backups}"

fix_runtime_permissions() {
  if [ "${ONEDU_FIX_VOLUME_OWNERSHIP:-1}" != "1" ]; then
    return
  fi

  mkdir -p "$STATIC_DIR" "$MEDIA_DIR" "$PRIVATE_MEDIA_DIR" "$PRIVATE_MEDIA_DIR/lesson_hls" "$LOG_DIR" "$BACKUP_DIR"
  touch "$LOG_DIR/onedu.log"

  chown "$APP_USER:$APP_GROUP" "$STATIC_DIR" "$MEDIA_DIR" "$PRIVATE_MEDIA_DIR" "$PRIVATE_MEDIA_DIR/lesson_hls" "$LOG_DIR" "$BACKUP_DIR"
  chown -R "$APP_USER:$APP_GROUP" "$STATIC_DIR" "$MEDIA_DIR" "$LOG_DIR" "$BACKUP_DIR"
  chmod u+rwX "$STATIC_DIR" "$MEDIA_DIR" "$PRIVATE_MEDIA_DIR" "$PRIVATE_MEDIA_DIR/lesson_hls" "$LOG_DIR" "$BACKUP_DIR"
  chmod -R u+rwX "$STATIC_DIR" "$MEDIA_DIR" "$LOG_DIR" "$BACKUP_DIR"
  chmod -R a+rX "$STATIC_DIR" "$MEDIA_DIR" "$PRIVATE_MEDIA_DIR"

  if [ "${ONEDU_FIX_HLS_OWNERSHIP:-1}" = "1" ]; then
    chown -R "$APP_USER:$APP_GROUP" "$PRIVATE_MEDIA_DIR/lesson_hls"
    chmod -R u+rwX "$PRIVATE_MEDIA_DIR/lesson_hls"
  fi
}

if [ "$(id -u)" = "0" ] && [ "${ONEDU_RUN_AS_ROOT:-0}" != "1" ]; then
  fix_runtime_permissions
  exec gosu "$APP_USER:$APP_GROUP" "$0" "$@"
fi

if [ "${DJANGO_WAIT_FOR_DB:-1}" = "1" ]; then
  python - <<'PY'
import time
import os
from django.db import connections
from django.db.utils import OperationalError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

for attempt in range(60):
    try:
        connections['default'].ensure_connection()
        break
    except OperationalError:
        if attempt == 59:
            raise
        time.sleep(1)
PY
fi

if [ "${DJANGO_RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
