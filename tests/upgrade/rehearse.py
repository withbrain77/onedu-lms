"""Run baseline on 4.2, then verify on 5.x and again on 4.2 before deployment.

Only synthetic data is used. Each verification requires an identical migration
graph and persisted business records, and checks passwords, sessions and files.
"""
import hashlib
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'browser'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.upgrade_test_settings'

import django
django.setup()

from django.apps import apps
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import serializers
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from accounts.models import User
from certificates.models import Certificate
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from progress.models import WatchProgress
from seed import seed

STATE = settings.UPGRADE_ROOT / 'state.json'


def records():
    result = {}
    for model in apps.get_models():
        if model._meta.label_lower == 'sessions.session':
            continue
        rows = json.loads(serializers.serialize('json', model.objects.order_by('pk')))
        if model == User:
            for row in rows:
                # Authentication can legitimately rehash passwords/update last_login.
                row['fields'].pop('password')
                row['fields'].pop('last_login')
        result[model._meta.label_lower] = rows
    return result


def files():
    result = {}
    for label, directory in [('public', settings.MEDIA_ROOT), ('private', settings.PRIVATE_MEDIA_ROOT)]:
        for path in sorted(Path(directory).rglob('*')):
            if path.is_file():
                result[f'{label}/{path.relative_to(directory).as_posix()}'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def migration_names():
    return sorted('/'.join(item) for item in MigrationExecutor(connection).loader.applied_migrations)


def verify_access(session_key=None):
    client = Client()
    if session_key:
        client.cookies[settings.SESSION_COOKIE_NAME] = session_key
        assert client.get('/accounts/profile/').status_code == 200, 'Existing session no longer works'
    user = authenticate(username='browserstudent', password='Browser-only-2026!')
    assert user is not None, 'Existing password no longer works'
    client.force_login(user)
    for url in ['/accounts/profile/', '/classroom/']:
        assert client.get(url).status_code == 200, url
    staff = authenticate(username='browseradmin', password='Browser-only-2026!')
    assert staff is not None, 'Existing admin password no longer works'
    admin_client = Client()
    admin_client.force_login(staff)
    for url in ['/admin/', '/admin/accounts/user/', '/admin/enrollments/enrollment/']:
        assert admin_client.get(url).status_code == 200, url
    return client.cookies[settings.SESSION_COOKIE_NAME].value


phase = sys.argv[1]
if phase == 'baseline':
    assert django.VERSION[:2] == (4, 2), 'Baseline must run on Django 4.2'
    assert not STATE.exists(), 'Use a fresh rehearsal workspace/database'
    call_command('migrate', verbosity=0, interactive=False)
    assert not User.objects.exists(), 'Rehearsal database must be empty'
    (ROOT / '.browser-tests').mkdir(exist_ok=True)
    seed(ROOT)
    student = User.objects.get(username='browserstudent')
    course = Course.objects.get(slug='browser-layout')
    enrollment = Enrollment.objects.get(user=student, course=course)
    lesson = Lesson.objects.get(course=course)
    lesson.video_file.save('rehearsal.mp4', ContentFile(b'synthetic-file-preservation-check'))
    WatchProgress.objects.filter(user=student, lesson=lesson).update(
        last_position_seconds=125, total_watched_seconds=125, duration_seconds=600, progress_percent=20)
    certificate = Certificate.objects.create(user=student, course=course, enrollment=enrollment)
    certificate.pdf_file.save('rehearsal.pdf', ContentFile(b'%PDF-1.4\nsynthetic-file-preservation-check'))
    session_key = verify_access()
    state = {'records': records(), 'files': files(), 'migrations': migration_names(), 'session': session_key}
    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
elif phase == 'verify':
    state = json.loads(STATE.read_text(encoding='utf-8'))
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes()), 'Upgrade introduces DB migrations: review before proceeding'
    assert migration_names() == state['migrations'], 'Applied migrations changed'
    assert records() == state['records'], 'Persisted business data changed'
    assert files() == state['files'], 'Uploaded files changed'
    state['session'] = verify_access(state['session'])
    after_access = records()
    # Classroom access refreshes enrollment access dates through save(), which
    # legitimately advances updated_at even when the actual dates are unchanged.
    expected_after_access = copy.deepcopy(state['records'])
    for expected, actual in zip(expected_after_access['enrollments.enrollment'], after_access['enrollments.enrollment']):
        expected['fields']['updated_at'] = actual['fields']['updated_at']
    assert after_access == expected_after_access, 'Read/authentication checks changed business data'
    assert files() == state['files'], 'Read/authentication checks changed uploaded files'
    state['records'] = after_access
    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
else:
    raise ValueError('Use baseline or verify')
print(f'Django {django.get_version()} / {connection.vendor}: {phase} passed; data, files, passwords, sessions and migrations verified.')
