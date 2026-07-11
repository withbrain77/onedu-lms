#!/bin/sh

# Read-only video playback diagnostics for the Synology Docker deployment.
# Usage:
#   cd /volume1/wbinstitute/docker/onedu/app
#   sh deploy/diagnose-video.sh
#
# Optional focused check:
#   LESSON_ID=1 USERNAME=student01 sh deploy/diagnose-video.sh

COMPOSE_PROJECT="${COMPOSE_PROJECT:-onedu}"
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
APP_DIR="${APP_DIR:-/volume1/wbinstitute/docker/onedu/app}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
HTTP_HOST="${HTTP_HOST:-192.168.0.97}"
LESSON_ID="${LESSON_ID:-}"
USERNAME="${USERNAME:-}"

cd "$APP_DIR" || {
  echo "Cannot cd to APP_DIR=$APP_DIR"
  exit 1
}

dc() {
  # Intentionally allow DOCKER_COMPOSE="sudo docker compose" for Synology users
  # who can SSH but are not allowed to access /var/run/docker.sock directly.
  # shellcheck disable=SC2086
  $DOCKER_COMPOSE -p "$COMPOSE_PROJECT" "$@"
}

section() {
  printf '\n\n===== %s =====\n' "$1"
}

run() {
  echo "+ $*"
  "$@" || true
}

section "Context"
echo "APP_DIR=$APP_DIR"
echo "COMPOSE_PROJECT=$COMPOSE_PROJECT"
echo "DOCKER_COMPOSE=$DOCKER_COMPOSE"
echo "BASE_URL=$BASE_URL"
echo "HTTP_HOST=$HTTP_HOST"
echo "LESSON_ID=${LESSON_ID:-not set}"
echo "USERNAME=${USERNAME:-not set}"

section "Docker Compose Services"
run dc ps

section "Django Settings"
dc exec -T web python manage.py shell <<'PY' || true
from django.conf import settings

print('DEBUG=', settings.DEBUG)
print('ALLOWED_HOSTS=', settings.ALLOWED_HOSTS)
print('CSRF_TRUSTED_ORIGINS=', settings.CSRF_TRUSTED_ORIGINS)
print('USE_X_ACCEL_REDIRECT=', settings.USE_X_ACCEL_REDIRECT)
print('X_ACCEL_REDIRECT_PREFIX=', settings.X_ACCEL_REDIRECT_PREFIX)
print('MEDIA_ROOT=', settings.MEDIA_ROOT)
print('PRIVATE_MEDIA_ROOT=', settings.PRIVATE_MEDIA_ROOT)
PY

section "Django Check"
run dc exec -T web python manage.py check

section "Courses and Lessons"
dc exec -T web python manage.py shell <<'PY' || true
from lessons.models import Lesson

for lesson in Lesson.objects.select_related('course').order_by('course_id', 'order', 'id'):
    print({
        'lesson_id': lesson.id,
        'course_id': lesson.course_id,
        'course_title': lesson.course.title,
        'course_is_public': lesson.course.is_public,
        'lesson_title': lesson.title,
        'lesson_is_public': lesson.is_public,
        'video_file': lesson.video_file.name if lesson.video_file else '',
        'watch_url': lesson.get_absolute_url(),
        'video_url': lesson.get_video_url(),
    })
PY

section "Enrollments"
dc exec -T web python manage.py shell <<'PY' || true
from enrollments.models import Enrollment

for enrollment in Enrollment.objects.select_related('user', 'course').order_by('course_id', 'user__username', 'id'):
    print({
        'enrollment_id': enrollment.id,
        'username': enrollment.user.username,
        'course_id': enrollment.course_id,
        'course_title': enrollment.course.title,
        'status': enrollment.status,
        'start_date': str(enrollment.start_date),
        'end_date': str(enrollment.end_date),
        'is_within_period': enrollment.is_within_period(),
        'has_ended': enrollment.has_ended,
    })
PY

section "Private Media Files from web"
run dc exec -T web sh -lc 'find /vol/web/private_media -maxdepth 5 -type f | sort | head -50'

section "Private Media Files from nginx"
run dc exec -T nginx sh -lc 'find /vol/web/private_media -maxdepth 5 -type f | sort | head -50'

section "Private Media Permissions"
run dc exec -T web sh -lc 'ls -la /vol/web/private_media; find /vol/web/private_media -maxdepth 2 -type d -exec ls -ld {} \; | head -30'
run dc exec -T nginx sh -lc 'ls -la /vol/web/private_media; find /vol/web/private_media -maxdepth 2 -type d -exec ls -ld {} \; | head -30'

section "Nginx Protected Media Config"
run sh -c 'sed -n "/protected-media/,+12p" deploy/nginx/default.conf'
run dc exec -T nginx sh -lc 'nginx -T 2>/dev/null | sed -n "/protected-media/,+12p"'

section "Public HTTP Checks"
run curl -I "$BASE_URL/"
run curl -I "$BASE_URL/courses/"
run curl -I "$BASE_URL/admin/"

if [ -n "$LESSON_ID" ] && [ -n "$USERNAME" ]; then
  section "Focused Lesson/User Access Check"
  dc exec -T \
    -e DIAG_LESSON_ID="$LESSON_ID" \
    -e DIAG_USERNAME="$USERNAME" \
    -e DIAG_HTTP_HOST="$HTTP_HOST" \
    web python manage.py shell <<'PY' || true
import os

from django.test import Client
from django.urls import reverse

from accounts.models import User
from lessons.models import Lesson

lesson_id = int(os.environ['DIAG_LESSON_ID'])
username = os.environ['DIAG_USERNAME']
http_host = os.environ['DIAG_HTTP_HOST']

lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
user = User.objects.get(username=username)
client = Client(HTTP_HOST=http_host)
client.force_login(user)

watch_url = lesson.get_absolute_url()
video_url = lesson.get_video_url()

print('lesson=', lesson.id, lesson.title)
print('course=', lesson.course.id, lesson.course.title, 'public=', lesson.course.is_public)
print('lesson_public=', lesson.is_public)
print('video_file=', lesson.video_file.name if lesson.video_file else '')
print('watch_url=', watch_url)
print('video_url=', video_url)

watch_response = client.get(watch_url)
print('watch_status=', watch_response.status_code)
print('watch_contains_video_url=', video_url in watch_response.content.decode('utf-8', errors='ignore'))

video_response = client.get(video_url)
print('video_status=', video_response.status_code)
for key, value in video_response.items():
    print(f'video_header_{key}={value}')
try:
    video_response.close()
except AttributeError:
    pass
PY
else
  section "Focused Lesson/User Access Check Skipped"
  echo "Set LESSON_ID and USERNAME to check a specific video request."
  echo "Example: LESSON_ID=1 USERNAME=student01 sh deploy/diagnose-video.sh"
fi

section "Recent web logs"
run dc logs web --tail=80

section "Recent nginx logs"
run dc logs nginx --tail=80

section "Done"
echo "Attach this output when asking for the next diagnosis step."
