#!/bin/sh

# Limited Onedu production operations wrapper.
# Install this as /usr/local/sbin/onedu-ops and allow only this command via sudo.

set -eu

APP_DIR="${ONEDU_APP_DIR:-/volume1/wbinstitute/docker/onedu/app}"
PROJECT="${ONEDU_COMPOSE_PROJECT:-onedu}"
DOCKER_BIN="${ONEDU_DOCKER_BIN:-/usr/local/bin/docker}"
BASE_URL="${ONEDU_BASE_URL:-http://127.0.0.1:8080}"
BACKUP_ROOT="${ONEDU_BACKUP_ROOT:-$APP_DIR/backups}"

compose() {
  cd "$APP_DIR"
  "$DOCKER_BIN" compose -p "$PROJECT" "$@"
}

ensure_data_dirs() {
  mkdir -p \
    "$APP_DIR/data/static" \
    "$APP_DIR/data/media" \
    "$APP_DIR/data/private_media" \
    "$APP_DIR/data/logs" \
    "$APP_DIR/data/postgres" \
    "$APP_DIR/data/redis"
}

usage() {
  cat <<'EOF'
Usage:
  onedu-ops <action>

Actions:
  status          Show compose service status
  config          Validate docker compose config
  check           Run Django system check
  logs            Show recent web/nginx/worker/redis logs
  logs-web        Show recent web logs
  logs-nginx      Show recent nginx logs
  logs-worker     Show recent worker logs
  logs-redis      Show recent redis logs
  restart-nginx   Restart nginx only
  restart-web     Restart web only
  restart-queue   Recreate redis and restart web/worker
  deploy          Build/start all services and run Django check
  health          Show status, check, and local HTTP headers
  readiness       Run ONEDU operational readiness checks
  backup-db       Create a PostgreSQL dump under backups/db
  backup-check    Show backup and data directory status
  hls-status      Show recent HLS conversion jobs
  hls-reset-stuck Mark pending jobs without task IDs as failed
  expiry-notices  Send 7-day enrollment expiry notice emails
EOF
}

case "${1:-help}" in
  help|-h|--help)
    usage
    ;;
  status)
    compose ps
    ;;
  config)
    compose config --quiet
    ;;
  check)
    compose exec -T web python manage.py check
    ;;
  logs)
    compose logs web --tail=80
    compose logs nginx --tail=80
    compose logs worker --tail=80
    compose logs redis --tail=50
    ;;
  logs-web)
    compose logs web --tail=150
    ;;
  logs-nginx)
    compose logs nginx --tail=150
    ;;
  logs-worker)
    compose logs worker --tail=150
    ;;
  logs-redis)
    compose logs redis --tail=120
    ;;
  restart-nginx)
    compose restart nginx
    ;;
  restart-web)
    compose restart web
    ;;
  restart-queue)
    compose up -d --force-recreate redis
    compose restart web worker
    ;;
  deploy)
    ensure_data_dirs
    compose config --quiet
    compose up -d --build --remove-orphans
    compose exec -T web python manage.py check
    compose restart nginx
    compose ps
    ;;
  health)
    compose ps
    compose exec -T web python manage.py check
    if command -v curl >/dev/null 2>&1; then
      curl -I "$BASE_URL/" || true
      curl -I "$BASE_URL/admin/" || true
    fi
    ;;
  readiness)
    compose exec -T web python manage.py ops_readiness
    ;;
  backup-db)
    mkdir -p "$BACKUP_ROOT/db"
    backup_file="$BACKUP_ROOT/db/onedu_$(date +%Y%m%d_%H%M%S).sql"
    compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup_file"
    chmod 0600 "$backup_file"
    ls -lh "$backup_file"
    ;;
  backup-check)
    mkdir -p "$BACKUP_ROOT/db" "$BACKUP_ROOT/media" "$BACKUP_ROOT/private_media"
    echo "Backup root: $BACKUP_ROOT"
    echo
    echo "Recent DB backups:"
    ls -lht "$BACKUP_ROOT/db" 2>/dev/null | head -10 || true
    echo
    echo "Data directory sizes:"
    du -sh "$APP_DIR/data/postgres" "$APP_DIR/data/media" "$APP_DIR/data/private_media" 2>/dev/null || true
    ;;
  hls-status)
    compose exec -T web python manage.py shell <<'PY'
from lessons.models import HLSConversionJob

for job in HLSConversionJob.objects.select_related('lesson').all().order_by('-created_at')[:20]:
    print(
        job.id,
        job.lesson_id,
        job.lesson.title,
        job.status,
        f'progress={job.progress_percent}%',
        f'time={job.progress_current_seconds}/{job.progress_total_seconds}s',
        'task=',
        job.celery_task_id or '-',
        'error=',
        (job.error_message or '')[:100],
    )
PY
    ;;
  hls-reset-stuck)
    compose exec -T web python manage.py shell <<'PY'
from django.utils import timezone
from lessons.models import HLSConversionJob

jobs = list(HLSConversionJob.objects.filter(status='pending', celery_task_id=''))
for job in jobs:
    job.status = 'failed'
    job.error_message = '관리자 조치: Celery 작업 ID 없이 대기 상태로 남아 재요청을 위해 실패 처리'
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])

print('updated', len(jobs))
PY
    ;;
  expiry-notices)
    compose exec -T web python manage.py send_expiry_notices
    ;;
  *)
    echo "Unknown action: $1"
    usage
    exit 2
    ;;
esac
