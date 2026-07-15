import socket
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.db.utils import DatabaseError, OperationalError, ProgrammingError
from django.utils import timezone

from accounts.models import AccessLog, User
from enrollments.models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from lessons.models import HLSConversionJob, Lesson, LessonAttachmentDownload


def _format_bytes(value):
    value = float(value or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} TB'


def _safe_count(queryset):
    try:
        return queryset.count()
    except (OperationalError, ProgrammingError):
        return 0


def _service(label, code, ok, detail='', tone=None):
    if tone is None:
        tone = 'ok' if ok else 'danger'
    return {
        'label': label,
        'code': code,
        'ok': ok,
        'tone': tone,
        'status_label': '정상' if ok else '확인 필요',
        'detail': detail,
    }


def _check_database():
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _service('데이터베이스', 'DB', True, f'응답 {elapsed_ms}ms')
    except DatabaseError as exc:
        return _service('데이터베이스', 'DB', False, str(exc)[:180])


def _check_redis():
    broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
    if not broker_url.startswith(('redis://', 'rediss://')):
        return _service('Redis / 작업 큐', 'RQ', False, 'Redis broker 설정이 아닙니다.', tone='warning')

    try:
        from redis import Redis

        timeout = max(float(getattr(settings, 'ONEDU_SERVER_STATUS_TIMEOUT_SECONDS', 1.0)), 0.2)
        client = Redis.from_url(
            broker_url,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        started = time.monotonic()
        client.ping()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _service('Redis / 작업 큐', 'RQ', True, f'응답 {elapsed_ms}ms')
    except Exception as exc:  # Redis can raise connection and URL parsing errors.
        return _service('Redis / 작업 큐', 'RQ', False, str(exc)[:180])


def _first_existing_parent(path):
    candidate = Path(path)
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _disk_item(label, path):
    configured_path = Path(path)
    existing_path = _first_existing_parent(configured_path)
    try:
        usage = shutil.disk_usage(existing_path)
    except OSError as exc:
        return {
            'label': label,
            'path': str(configured_path),
            'exists': configured_path.exists(),
            'ok': False,
            'tone': 'danger',
            'detail': str(exc)[:180],
            'used_percent': 0,
            'used_label': '-',
            'total_label': '-',
            'free_label': '-',
        }

    used = usage.total - usage.free
    used_percent = round((used / usage.total) * 100, 1) if usage.total else 0
    tone = 'ok'
    if used_percent >= 90:
        tone = 'danger'
    elif used_percent >= 80 or not configured_path.exists():
        tone = 'warning'

    return {
        'label': label,
        'path': str(configured_path),
        'checked_path': str(existing_path),
        'exists': configured_path.exists(),
        'ok': tone == 'ok',
        'tone': tone,
        'used_percent': used_percent,
        'used_label': _format_bytes(used),
        'total_label': _format_bytes(usage.total),
        'free_label': _format_bytes(usage.free),
        'detail': '정상' if configured_path.exists() else '설정 경로가 아직 생성되지 않았습니다.',
    }


def _storage_status():
    return [
        _disk_item('static', settings.STATIC_ROOT),
        _disk_item('media', settings.MEDIA_ROOT),
        _disk_item('private_media', settings.PRIVATE_MEDIA_ROOT),
    ]


def _resolve_domain(domain):
    if not domain:
        return []
    try:
        return sorted(set(socket.gethostbyname_ex(domain)[2]))
    except OSError:
        return []


def _public_ip():
    check_url = getattr(settings, 'ONEDU_PUBLIC_IP_CHECK_URL', '').strip()
    if not check_url:
        return '', '공인 IP 확인 URL이 설정되지 않았습니다.'
    timeout = max(float(getattr(settings, 'ONEDU_SERVER_STATUS_TIMEOUT_SECONDS', 1.0)), 0.2)
    try:
        with urlopen(check_url, timeout=timeout) as response:
            value = response.read(80).decode('utf-8', errors='ignore').strip()
        return value, ''
    except Exception as exc:  # Network checks must not break the admin page.
        return '', str(exc)[:180]


def _local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return ''


def _network_status(request):
    site_url = getattr(settings, 'PUBLIC_SITE_URL', '')
    effective_site_url = site_url
    if not effective_site_url and request:
        effective_site_url = request.build_absolute_uri('/')
    try:
        request_host = request.get_host().split(':')[0] if request else ''
    except DisallowedHost:
        request_host = ''
    parsed_host = urlparse(site_url).hostname if site_url else ''
    domain = getattr(settings, 'ONEDU_SERVER_STATUS_DOMAIN', '') or parsed_host or request_host
    dns_ips = _resolve_domain(domain)
    public_ip, public_ip_error = _public_ip()
    mismatch = bool(public_ip and dns_ips and public_ip not in dns_ips)

    return {
        'domain': domain or '-',
        'site_url': effective_site_url,
        'dns_ips': dns_ips,
        'public_ip': public_ip,
        'public_ip_error': public_ip_error,
        'local_ip': _local_ip(),
        'mismatch': mismatch,
        'tone': 'danger' if mismatch else 'ok',
        'summary': 'DNS와 공인 IP가 일치합니다.' if public_ip and not mismatch else (
            'DNS와 공인 IP가 다릅니다.' if mismatch else '공인 IP 비교가 비활성화되어 있습니다.'
        ),
    }


def _traffic_summary():
    now = timezone.now()
    today_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    day_ago = now - timezone.timedelta(hours=24)
    fifteen_minutes_ago = now - timezone.timedelta(minutes=15)

    today_logs = AccessLog.objects.filter(created_at__gte=today_start)
    recent_logs = AccessLog.objects.filter(created_at__gte=fifteen_minutes_ago)
    hls_today = today_logs.filter(event_type=AccessLog.EventType.HLS_PLAYLIST)
    video_today = today_logs.filter(event_type=AccessLog.EventType.VIDEO_ACCESS)
    downloads_today = LessonAttachmentDownload.objects.filter(downloaded_at__gte=today_start)

    return {
        'today_access_count': _safe_count(today_logs),
        'recent_access_count': _safe_count(recent_logs),
        'today_unique_users': _safe_count(today_logs.values('user_id').distinct()),
        'today_unique_ips': _safe_count(today_logs.values('ip_address').distinct()),
        'today_hls_starts': _safe_count(hls_today),
        'today_video_accesses': _safe_count(video_today),
        'today_downloads': _safe_count(downloads_today),
        'last_24h_access_count': _safe_count(AccessLog.objects.filter(created_at__gte=day_ago)),
        'note': 'HLS 세그먼트 전송량은 Nginx 로그 기반 연동 전까지 요청 수 중심으로 확인합니다.',
    }


def _application_summary():
    now = timezone.now()
    today = timezone.localdate()
    return {
        'users': User.objects.count(),
        'active_enrollments': _safe_count(
            Enrollment.objects.filter(
                status=Enrollment.Status.APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            )
        ),
        'pending_enrollments': _safe_count(Enrollment.objects.filter(status=Enrollment.Status.REQUESTED)),
        'pending_reenrollments': _safe_count(
            ReEnrollmentRequest.objects.filter(status=ReEnrollmentRequest.Status.PENDING)
        ),
        'lessons': Lesson.objects.count(),
        'hls_pending': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.PENDING)),
        'hls_running': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.RUNNING)),
        'hls_failed': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.FAILED)),
        'email_failed_24h': _safe_count(
            EmailDeliveryLog.objects.filter(
                status=EmailDeliveryLog.Status.FAILED,
                created_at__gte=now - timezone.timedelta(hours=24),
            )
        ),
        'suspicious_24h': _safe_count(
            AccessLog.objects.filter(is_suspicious=True, created_at__gte=now - timezone.timedelta(hours=24))
        ),
        'x_accel_enabled': bool(getattr(settings, 'USE_X_ACCEL_REDIRECT', False)),
    }


def _build_warnings(services, storage, network, app):
    warnings = []
    for service in services:
        if not service['ok']:
            warnings.append({'tone': service['tone'], 'message': f"{service['label']} 상태를 확인하세요. {service['detail']}"})
    for item in storage:
        if item['tone'] == 'danger':
            warnings.append({'tone': 'danger', 'message': f"{item['label']} 저장소 사용량이 {item['used_percent']}%입니다."})
        elif item['tone'] == 'warning':
            warnings.append({'tone': 'warning', 'message': f"{item['label']} 저장소를 확인하세요. {item['detail']}"})
    if network['mismatch']:
        warnings.append({'tone': 'danger', 'message': '도메인 DNS IP와 현재 공인 IP가 일치하지 않습니다.'})
    if app['hls_failed']:
        warnings.append({'tone': 'warning', 'message': f"HLS 변환 실패 작업이 {app['hls_failed']}건 있습니다."})
    if app['email_failed_24h']:
        warnings.append({'tone': 'warning', 'message': f"최근 24시간 메일 발송 실패가 {app['email_failed_24h']}건 있습니다."})
    if app['suspicious_24h']:
        warnings.append({'tone': 'warning', 'message': f"최근 24시간 접속 보안 주의 기록이 {app['suspicious_24h']}건 있습니다."})
    if not app['x_accel_enabled']:
        warnings.append({'tone': 'warning', 'message': '운영 환경에서 X-Accel-Redirect 영상 보호 설정을 확인하세요.'})
    if not warnings:
        warnings.append({'tone': 'ok', 'message': '현재 즉시 조치가 필요한 운영 경고는 없습니다.'})
    return warnings


def build_server_status(request=None):
    services = [_check_database(), _check_redis()]
    storage = _storage_status()
    network = _network_status(request)
    traffic = _traffic_summary()
    app = _application_summary()
    warnings = _build_warnings(services, storage, network, app)

    if any(item['tone'] == 'danger' for item in warnings):
        overall_tone = 'danger'
        overall_label = '위험'
    elif any(item['tone'] == 'warning' for item in warnings):
        overall_tone = 'warning'
        overall_label = '주의'
    else:
        overall_tone = 'ok'
        overall_label = '정상'

    return {
        'checked_at': timezone.now(),
        'overall_tone': overall_tone,
        'overall_label': overall_label,
        'services': services,
        'storage': storage,
        'network': network,
        'traffic': traffic,
        'app': app,
        'warnings': warnings,
    }
