#!/bin/sh

# Safe remote operations wrapper for the Synology Onedu deployment.
#
# This script does not store credentials. Configure SSH outside the repo:
#   ~/.ssh/config
#     Host onedu-nas
#       HostName 192.168.0.97
#       User your-nas-user
#       IdentityFile ~/.ssh/onedu_nas_ed25519
#
# Usage:
#   ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh status
#   ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh diagnose-video
#   ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh diagnose-video 1 student01

set -eu

SSH_TARGET="${ONEDU_SSH_TARGET:-}"
APP_DIR="${ONEDU_APP_DIR:-/volume1/wbinstitute/docker/onedu/app}"
COMPOSE_PROJECT="${ONEDU_COMPOSE_PROJECT:-onedu}"
DOCKER_COMPOSE="${ONEDU_DOCKER_COMPOSE:-docker compose}"
REMOTE_OPS="${ONEDU_REMOTE_OPS:-sudo -n /usr/local/sbin/onedu-ops}"
BASE_URL="${ONEDU_BASE_URL:-http://127.0.0.1:8080}"
HTTP_HOST="${ONEDU_HTTP_HOST:-192.168.0.97}"

if [ -z "$SSH_TARGET" ]; then
  echo "ONEDU_SSH_TARGET is required. Example:"
  echo "  ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh status"
  exit 2
fi

ACTION="${1:-help}"
LESSON_ID="${2:-}"
USERNAME="${3:-}"

remote() {
  ssh "$SSH_TARGET" "$@"
}

run_in_app() {
  remote "cd '$APP_DIR' && $*"
}

compose() {
  run_in_app "$DOCKER_COMPOSE -p '$COMPOSE_PROJECT' $*"
}

ops() {
  remote "$REMOTE_OPS $*"
}

case "$ACTION" in
  help|-h|--help)
    cat <<EOF
Usage:
  ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh <action>

Actions:
  status                         Show docker compose service status
  check                          Run python manage.py check
  test                           Run python manage.py test
  deploy-check                   Run python manage.py check --deploy
  compose-config                 Validate docker compose config
  logs                           Show recent web/nginx logs
  deploy                         Build/start services through onedu-ops
  health                         Run service and HTTP health checks
  readiness                      Run ONEDU operational readiness checks
  backup-db                      Create a DB backup on the NAS
  backup-check                   Show backup and data directory status
  restart-nginx                  Restart nginx through onedu-ops
  restart-queue                  Recreate redis and restart queue services
  hls-status                     Show recent HLS conversion jobs
  hls-reset-stuck                Mark pending HLS jobs without task IDs as failed
  expiry-notices                 Send 7-day enrollment expiry notice emails
  tail                           Follow web/nginx logs
  diagnose-video                 Run full video diagnostics
  diagnose-video LESSON USERNAME Run focused video diagnostics
  video-headers LESSON USERNAME  Print video view status and headers only
EOF
    ;;
  status)
    ops status
    ;;
  check)
    ops check
    ;;
  test)
    compose exec -T web python manage.py test
    ;;
  deploy-check)
    compose exec -T web python manage.py check --deploy
    ;;
  compose-config)
    ops config
    ;;
  logs)
    ops logs
    ;;
  deploy)
    ops deploy
    ;;
  health)
    ops health
    ;;
  readiness)
    ops readiness
    ;;
  backup-db)
    ops backup-db
    ;;
  backup-check)
    ops backup-check
    ;;
  restart-nginx)
    ops restart-nginx
    ;;
  restart-queue)
    ops restart-queue
    ;;
  hls-status)
    ops hls-status
    ;;
  hls-reset-stuck)
    ops hls-reset-stuck
    ;;
  expiry-notices)
    ops expiry-notices
    ;;
  tail)
    compose logs -f web nginx
    ;;
  diagnose-video)
    if [ -n "$LESSON_ID" ] && [ -n "$USERNAME" ]; then
      run_in_app "DOCKER_COMPOSE='$DOCKER_COMPOSE' LESSON_ID='$LESSON_ID' USERNAME='$USERNAME' BASE_URL='$BASE_URL' HTTP_HOST='$HTTP_HOST' sh deploy/diagnose-video.sh"
    else
      run_in_app "DOCKER_COMPOSE='$DOCKER_COMPOSE' BASE_URL='$BASE_URL' HTTP_HOST='$HTTP_HOST' sh deploy/diagnose-video.sh"
    fi
    ;;
  video-headers)
    if [ -z "$LESSON_ID" ] || [ -z "$USERNAME" ]; then
      echo "video-headers requires LESSON_ID and USERNAME."
      echo "Example: ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh video-headers 1 student01"
      exit 2
    fi
    compose exec -T \
      -e DIAG_LESSON_ID="$LESSON_ID" \
      -e DIAG_USERNAME="$USERNAME" \
      -e DIAG_HTTP_HOST="$HTTP_HOST" \
      web python manage.py shell <<'PY'
import os

from django.test import Client
from accounts.models import User
from lessons.models import Lesson

lesson = Lesson.objects.select_related('course').get(pk=int(os.environ['DIAG_LESSON_ID']))
user = User.objects.get(username=os.environ['DIAG_USERNAME'])
client = Client(HTTP_HOST=os.environ['DIAG_HTTP_HOST'])
client.force_login(user)

for label, url in [('watch', lesson.get_absolute_url()), ('video', lesson.get_video_url())]:
    response = client.get(url)
    print(label, url, response.status_code)
    for key, value in response.items():
        print(f'{label}_header_{key}={value}')
    try:
        response.close()
    except AttributeError:
        pass
PY
    ;;
  *)
    echo "Unknown action: $ACTION"
    echo "Run with --help for available actions."
    exit 2
    ;;
esac
