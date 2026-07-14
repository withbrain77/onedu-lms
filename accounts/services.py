import hashlib
import ipaddress
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import AccessLog


logger = logging.getLogger(__name__)


def _clean_ip(value):
    if not value:
        return None
    candidate = value.strip().split(',')[0].strip()
    if candidate.startswith('[') and ']' in candidate:
        candidate = candidate[1:candidate.index(']')]
    elif candidate.count(':') == 1 and '.' in candidate:
        candidate = candidate.rsplit(':', 1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    real_ip = request.META.get('HTTP_X_REAL_IP', '')
    remote_addr = request.META.get('REMOTE_ADDR', '')
    return _clean_ip(forwarded_for) or _clean_ip(real_ip) or _clean_ip(remote_addr)


def summarize_user_agent(user_agent):
    value = (user_agent or '').strip()
    if not value:
        return '알 수 없는 기기'

    lower = value.lower()
    if 'iphone' in lower:
        device = 'iPhone'
    elif 'ipad' in lower:
        device = 'iPad'
    elif 'android' in lower and 'mobile' in lower:
        device = 'Android Phone'
    elif 'android' in lower:
        device = 'Android Tablet'
    elif 'windows' in lower:
        device = 'Windows PC'
    elif 'macintosh' in lower or 'mac os' in lower:
        device = 'Mac'
    elif 'linux' in lower:
        device = 'Linux'
    else:
        device = '기기'

    if 'edg/' in lower or 'edge/' in lower:
        browser = 'Edge'
    elif 'chrome/' in lower and 'chromium' not in lower:
        browser = 'Chrome'
    elif 'firefox/' in lower:
        browser = 'Firefox'
    elif 'safari/' in lower:
        browser = 'Safari'
    elif 'kakaotalk' in lower:
        browser = 'KakaoTalk'
    elif 'naver' in lower:
        browser = 'Naver'
    else:
        browser = '브라우저'

    return f'{device} / {browser}'


def _session_key(request):
    session = getattr(request, 'session', None)
    if session is None:
        return ''
    if not session.session_key:
        try:
            session.save()
        except Exception:
            return ''
    return session.session_key or ''


def _course_snapshot(course):
    if course is None:
        return None, ''
    return course.pk, course.title


def _lesson_snapshot(lesson):
    if lesson is None:
        return None, ''
    return lesson.pk, lesson.title


def _recent_other_environment_exists(user, session_key, ip_address, user_agent, minutes):
    if minutes <= 0 or getattr(user, 'is_staff', False):
        return False

    since = timezone.now() - timedelta(minutes=minutes)
    queryset = AccessLog.objects.filter(user=user, created_at__gte=since)
    if session_key:
        queryset = queryset.exclude(session_key__in=['', session_key])
    if ip_address or user_agent:
        queryset = queryset.exclude(ip_address=ip_address, user_agent=user_agent)
    return queryset.exists()


def _fingerprint(user_agent):
    return hashlib.sha256((user_agent or '').encode('utf-8')).hexdigest()[:12]


def record_access_log(request, event_type, course=None, lesson=None):
    if not getattr(settings, 'ONEDU_ACCESS_LOG_ENABLED', True):
        return None
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None

    try:
        ip_address = get_client_ip(request)
        user_agent = (request.META.get('HTTP_USER_AGENT', '') or '')[:1000]
        session_key = _session_key(request)
        window_minutes = getattr(settings, 'ONEDU_ACCESS_LOG_CONCURRENCY_WINDOW_MINUTES', 15)
        is_suspicious = _recent_other_environment_exists(
            user,
            session_key,
            ip_address,
            user_agent,
            window_minutes,
        )
        course_id, course_title = _course_snapshot(course)
        lesson_id, lesson_title = _lesson_snapshot(lesson)
        reason = ''
        if is_suspicious:
            reason = f'최근 {window_minutes}분 내 다른 접속 환경 기록이 있습니다.'
        return AccessLog.objects.create(
            user=user,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            device_summary=summarize_user_agent(user_agent),
            session_key=session_key,
            path=request.get_full_path()[:500],
            course_id_value=course_id,
            course_title=course_title,
            lesson_id_value=lesson_id,
            lesson_title=lesson_title,
            is_suspicious=is_suspicious,
            suspicious_reason=reason,
        )
    except Exception:
        logger.exception(
            'Failed to record access log for user_agent_hash=%s',
            _fingerprint(request.META.get('HTTP_USER_AGENT', '')),
        )
        return None
