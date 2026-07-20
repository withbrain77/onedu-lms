from datetime import timedelta

from django import template
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from django.db.utils import OperationalError, ProgrammingError
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import AccessLog, User
from certificates.models import Certificate
from courses.models import Course
from enrollments.models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from lessons.models import HLSConversionJob, Lesson, LessonAttachmentDownload
from progress.models import WatchProgress

register = template.Library()


MODEL_LABELS = {
    ('accounts', 'user'): '사용자',
    ('accounts', 'accountwithdrawalrequest'): '계정 탈퇴 요청',
    ('accounts', 'accesslog'): '접속 보안 로그',
    ('auth', 'group'): '그룹 및 권한',
    ('core', 'notice'): '공지사항',
    ('courses', 'course'): '강의',
    ('courses', 'courseinvitation'): '강의 초대 회원',
    ('lessons', 'lesson'): '차시',
    ('lessons', 'lessonattachment'): '학습 자료',
    ('lessons', 'lessonattachmentdownload'): '자료 다운로드 이력',
    ('lessons', 'hlsconversionjob'): 'HLS 변환 작업',
    ('enrollments', 'enrollment'): '수강 신청',
    ('enrollments', 'reenrollmentrequest'): '재수강 신청',
    ('enrollments', 'emaildeliverylog'): '메일 발송 로그',
    ('progress', 'watchprogress'): '시청 진도',
    ('quizzes', 'quiz'): '시험',
    ('quizzes', 'question'): '문제',
    ('quizzes', 'answerchoice'): '객관식 보기',
    ('quizzes', 'quizattempt'): '시험 응시',
    ('certificates', 'certificate'): '수료증',
}


MENU_GROUPS = [
    {
        'title': '회원 관리',
        'icon': 'A',
        'items': [('accounts', 'user'), ('accounts', 'accountwithdrawalrequest'), ('accounts', 'accesslog'), ('auth', 'group')],
    },
    {
        'title': '프로그램 관리',
        'icon': 'P',
        'items': [
            ('courses', 'course'),
            ('courses', 'courseinvitation'),
            ('lessons', 'lesson'),
            ('lessons', 'lessonattachment'),
            ('lessons', 'lessonattachmentdownload'),
            ('lessons', 'hlsconversionjob'),
            ('core', 'notice'),
        ],
    },
    {
        'title': '수강 관리',
        'icon': 'E',
        'items': [
            ('enrollments', 'enrollment'),
            ('enrollments', 'reenrollmentrequest'),
            ('enrollments', 'emaildeliverylog'),
            ('progress', 'watchprogress'),
        ],
    },
    {
        'title': '평가 관리',
        'icon': 'Q',
        'items': [
            ('quizzes', 'quiz'),
            ('quizzes', 'question'),
            ('quizzes', 'answerchoice'),
            ('quizzes', 'quizattempt'),
        ],
    },
    {
        'title': '수료 관리',
        'icon': 'C',
        'items': [('certificates', 'certificate')],
    },
]


QUICK_ACTIONS = [
    ('프로그램 등록', ('courses', 'course'), 'add_url', '새 강의/프로그램을 등록합니다.'),
    ('차시 등록', ('lessons', 'lesson'), 'add_url', '영상 차시를 추가합니다.'),
    ('학습 자료 등록', ('lessons', 'lessonattachment'), 'add_url', '교재와 슬라이드 자료를 등록합니다.'),
    ('공지사항 등록', ('core', 'notice'), 'add_url', '전체 또는 강의별 공지를 등록합니다.'),
    ('수강 신청 관리', ('enrollments', 'enrollment'), 'admin_url', '승인 대기와 수강 기간을 확인합니다.'),
    ('회원 검색', ('accounts', 'user'), 'admin_url', '수강생과 관리자 계정을 검색합니다.'),
    ('수료증 관리', ('certificates', 'certificate'), 'admin_url', '발급 상태와 검증 정보를 확인합니다.'),
]


def _model_map(app_list):
    mapping = {}
    for app in app_list:
        app_label = app.get('app_label')
        for model in app.get('models', []):
            key = (app_label, model.get('object_name', '').lower())
            mapping[key] = {
                **model,
                'app_label': app_label,
                'label': MODEL_LABELS.get(key, model.get('name')),
            }
    return mapping


def _reverse_admin(name, args=None):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ''


def _safe_count(queryset):
    try:
        return queryset.count()
    except (OperationalError, ProgrammingError):
        return 0


def _build_menu(request, app_list, models):
    current_path = request.path if request else ''
    dashboard_active = current_path.rstrip('/') == reverse('admin:index').rstrip('/')
    try:
        mobile_ops_url = reverse('admin_mobile_ops')
    except NoReverseMatch:
        mobile_ops_url = ''
    try:
        server_ops_url = reverse('admin_server_ops')
    except NoReverseMatch:
        server_ops_url = ''
    try:
        server_logs_url = reverse('admin_server_logs')
    except NoReverseMatch:
        server_logs_url = ''
    sections = [
        {
            'title': '대시보드',
            'icon': 'D',
            'is_dashboard': True,
            'is_active': dashboard_active,
            'items': [
                {
                    'label': '운영 현황',
                    'url': reverse('admin:index'),
                    'is_active': dashboard_active,
                    'can_add': False,
                }
            ],
        }
    ]
    if mobile_ops_url:
        mobile_ops_active = current_path.rstrip('/') == mobile_ops_url.rstrip('/')
        sections.append(
            {
                'title': '모바일 운영',
                'icon': 'M',
                'is_active': mobile_ops_active,
                'items': [
                    {
                        'label': '간편 운영 화면',
                        'url': mobile_ops_url,
                        'add_url': '',
                        'is_active': mobile_ops_active,
                        'can_add': False,
                    }
                ],
            }
        )
    server_ops_active = bool(server_ops_url and current_path.rstrip('/') == server_ops_url.rstrip('/'))
    server_logs_active = bool(server_logs_url and current_path.rstrip('/') == server_logs_url.rstrip('/'))
    operations_active = server_ops_active or server_logs_active
    assigned = set()
    for group in MENU_GROUPS:
        items = []
        for key in group['items']:
            model = models.get(key)
            if not model:
                continue
            assigned.add(key)
            url = model.get('admin_url') or ''
            is_active = bool(url and current_path.startswith(url))
            items.append(
                {
                    'label': model['label'],
                    'url': url,
                    'add_url': model.get('add_url') or '',
                    'is_active': is_active,
                    'can_add': bool(model.get('perms', {}).get('add') and model.get('add_url')),
                }
            )
        if items:
            sections.append(
                {
                    'title': group['title'],
                    'icon': group['icon'],
                    'is_active': any(item['is_active'] for item in items),
                    'items': items,
                }
            )

    extra_items = []
    for key, model in models.items():
        if key in assigned:
            continue
        url = model.get('admin_url') or ''
        extra_items.append(
            {
                'label': model['label'],
                'url': url,
                'add_url': model.get('add_url') or '',
                'is_active': bool(url and current_path.startswith(url)),
                'can_add': bool(model.get('perms', {}).get('add') and model.get('add_url')),
            }
        )
    if extra_items:
        sections.append(
            {
                'title': '기타 관리',
                'icon': 'M',
                'is_active': any(item['is_active'] for item in extra_items),
                'items': extra_items,
            }
        )

    operations_items = []
    if server_ops_url:
        operations_items.append(
            {
                'label': '서버 상태',
                'url': server_ops_url,
                'add_url': '',
                'is_active': server_ops_active,
                'can_add': False,
            }
        )
    if server_logs_url:
        operations_items.append(
            {
                'label': '서버 로그',
                'url': server_logs_url,
                'add_url': '',
                'is_active': server_logs_active,
                'can_add': False,
            }
        )
    operations_items.append(
        {
            'label': '사이트 보기',
            'url': '/',
            'add_url': '',
            'is_active': False,
            'can_add': False,
        }
    )
    sections.append(
        {
            'title': '운영 설정',
            'icon': 'S',
            'is_active': operations_active,
            'items': operations_items,
        }
    )
    return sections


def _build_stats(models):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    active_enrollments = Enrollment.objects.filter(
        status=Enrollment.Status.APPROVED,
        start_date__lte=today,
        end_date__gte=today,
    )
    stats = [
        {
            'label': '전체 회원',
            'value': User.objects.count(),
            'description': '등록된 수강생과 관리자',
            'url': models.get(('accounts', 'user'), {}).get('admin_url', ''),
            'icon': 'U',
        },
        {
            'label': '승인 대기',
            'value': Enrollment.objects.filter(
                status=Enrollment.Status.REQUESTED,
                course__pricing_type=Course.PricingType.PAID,
            ).count(),
            'description': '처리가 필요한 유료 수강 신청',
            'url': (models.get(('enrollments', 'enrollment'), {}).get('admin_url') or '') + '?status__exact=requested',
            'icon': 'W',
            'tone': 'warning',
        },
        {
            'label': '입금 대기',
            'value': Enrollment.objects.filter(
                status=Enrollment.Status.REQUESTED,
                course__pricing_type=Course.PricingType.PAID,
                payment_status=Enrollment.PaymentStatus.PENDING,
            ).count(),
            'description': '입금 확인이 필요한 유료 신청',
            'url': (models.get(('enrollments', 'enrollment'), {}).get('admin_url') or '') + '?status__exact=requested&payment_status__exact=pending',
            'icon': '₩',
            'tone': 'warning',
        },
        {
            'label': '수강 기간 내',
            'value': active_enrollments.values('user_id').distinct().count(),
            'description': '수강 기간 내 승인 수강생',
            'url': models.get(('enrollments', 'enrollment'), {}).get('admin_url', ''),
            'icon': 'L',
        },
        {
            'label': '운영 중 프로그램',
            'value': Course.objects.filter(is_public=True).count(),
            'description': '공개 상태의 강의',
            'url': models.get(('courses', 'course'), {}).get('admin_url', ''),
            'icon': 'P',
        },
        {
            'label': '등록 차시',
            'value': Lesson.objects.count(),
            'description': '등록된 영상 차시',
            'url': models.get(('lessons', 'lesson'), {}).get('admin_url', ''),
            'icon': 'V',
        },
        {
            'label': '이번 달 수료',
            'value': Enrollment.objects.filter(is_completed=True, completed_at__date__gte=month_start).count(),
            'description': '이번 달 수료 처리 인원',
            'url': models.get(('certificates', 'certificate'), {}).get('admin_url', ''),
            'icon': 'C',
        },
        {
            'label': '주의 접속',
            'value': AccessLog.objects.filter(
                is_suspicious=True,
                created_at__gte=timezone.now() - timedelta(days=7),
            ).count(),
            'description': '최근 7일 다른 접속 환경 의심',
            'url': (models.get(('accounts', 'accesslog'), {}).get('admin_url') or '') + '?is_suspicious__exact=1',
            'icon': 'S',
            'tone': 'warning',
        },
    ]
    return stats


def _build_pending_enrollments(models, limit=5):
    enrollment_model = models.get(('enrollments', 'enrollment'))
    if not enrollment_model:
        return {'count': 0, 'items': [], 'url': ''}

    base_url = enrollment_model.get('admin_url') or ''
    queryset = (
        Enrollment.objects
        .filter(status=Enrollment.Status.REQUESTED, course__pricing_type=Course.PricingType.PAID)
        .select_related('user', 'course')
        .order_by('-created_at')
    )
    items = []
    for enrollment in queryset[:limit]:
        change_url = _reverse_admin('admin:enrollments_enrollment_change', args=[enrollment.pk])
        items.append(
            {
                'student_name': enrollment.user.display_name,
                'student_username': enrollment.user.username,
                'student_email': enrollment.user.email,
                'course_title': enrollment.course.title,
                'created_at': enrollment.created_at,
                'status_label': enrollment.get_status_display(),
                'request_type': '무료 과정' if enrollment.course.is_free else '유료 과정',
                'payment_status': enrollment.get_payment_status_display(),
                'change_url': change_url,
            }
        )
    return {
        'count': queryset.count(),
        'items': items,
        'url': base_url + '?status__exact=requested',
    }


def _build_quick_actions(models):
    actions = []
    for label, key, url_key, description in QUICK_ACTIONS:
        model = models.get(key)
        if not model:
            continue
        url = model.get(url_key) or model.get('admin_url') or ''
        if not url:
            continue
        actions.append(
            {
                'label': label,
                'description': description,
                'url': url,
            }
        )
    return actions


def _build_courses(models, limit=5):
    course_model = models.get(('courses', 'course'))
    if not course_model:
        return {'items': [], 'url': ''}

    courses = (
        Course.objects
        .annotate(
            admin_lesson_count=Count('lessons', distinct=True),
            admin_enrollment_count=Count(
                'enrollments',
                filter=Q(enrollments__status=Enrollment.Status.APPROVED),
                distinct=True,
            ),
            admin_pending_count=Count(
                'enrollments',
                filter=Q(enrollments__status=Enrollment.Status.REQUESTED),
                distinct=True,
            ),
            admin_completed_count=Count(
                'enrollments',
                filter=Q(enrollments__is_completed=True),
                distinct=True,
            ),
        )
        .order_by('-updated_at', '-created_at')[:limit]
    )
    items = []
    for course in courses:
        change_url = _reverse_admin('admin:courses_course_change', args=[course.pk])
        items.append(
            {
                'title': course.title,
                'is_public': course.is_public,
                'visibility_label': course.visibility_label,
                'lesson_count': course.admin_lesson_count,
                'enrollment_count': course.admin_enrollment_count,
                'pending_count': course.admin_pending_count,
                'completed_count': course.admin_completed_count,
                'period': course.access_period_label,
                'change_url': change_url,
            }
        )
    return {
        'items': items,
        'url': course_model.get('admin_url') or '',
    }


def _build_active_watchers(models, limit=8):
    progress_model = models.get(('progress', 'watchprogress'))
    progress_url = progress_model.get('admin_url', '') if progress_model else ''
    cutoff_minutes = 2
    cutoff = timezone.now() - timedelta(minutes=cutoff_minutes)
    queryset = (
        WatchProgress.objects
        .filter(last_watched_at__gte=cutoff)
        .select_related('user', 'lesson', 'lesson__course', 'enrollment')
        .order_by('-last_watched_at')
    )

    try:
        count = queryset.values('user_id').distinct().count()
        recent_progress = list(queryset[:limit])
    except (OperationalError, ProgrammingError):
        return {'count': 0, 'items': [], 'url': progress_url, 'cutoff_minutes': cutoff_minutes}

    items = []
    for progress in recent_progress:
        items.append(
            {
                'student_name': progress.user.display_name,
                'student_username': progress.user.username,
                'course_title': progress.lesson.course.title,
                'lesson_title': progress.lesson.title,
                'progress_percent': progress.progress_percent,
                'last_position_seconds': progress.last_position_seconds,
                'total_watched_seconds': progress.total_watched_seconds,
                'last_watched_at': progress.last_watched_at,
                'progress_url': _reverse_admin('admin:progress_watchprogress_change', args=[progress.pk]),
                'user_url': _reverse_admin('admin:accounts_user_change', args=[progress.user_id]),
            }
        )

    return {
        'count': count,
        'items': items,
        'url': progress_url,
        'cutoff_minutes': cutoff_minutes,
    }


def _build_recent_activity(limit=10):
    return (
        LogEntry.objects
        .select_related('content_type', 'user')
        .order_by('-action_time')[:limit]
    )


def _build_hls_summary(models):
    hls_url = models.get(('lessons', 'hlsconversionjob'), {}).get('admin_url', '')
    return {
        'pending': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.PENDING)),
        'running': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.RUNNING)),
        'failed': _safe_count(HLSConversionJob.objects.filter(status=HLSConversionJob.Status.FAILED)),
        'url': hls_url,
    }


def _build_access_log_summary(models):
    access_log_url = models.get(('accounts', 'accesslog'), {}).get('admin_url', '')
    suspicious_url = access_log_url + '?is_suspicious__exact=1' if access_log_url else ''
    return {
        'suspicious_count': _safe_count(AccessLog.objects.filter(is_suspicious=True)),
        'recent_count': _safe_count(AccessLog.objects.filter(created_at__gte=timezone.now() - timedelta(days=1))),
        'url': access_log_url,
        'suspicious_url': suspicious_url,
    }


def _build_email_summary(models):
    email_log_url = models.get(('enrollments', 'emaildeliverylog'), {}).get('admin_url', '')
    return {
        'failed_count': _safe_count(EmailDeliveryLog.objects.filter(status=EmailDeliveryLog.Status.FAILED)),
        'skipped_count': _safe_count(EmailDeliveryLog.objects.filter(status=EmailDeliveryLog.Status.SKIPPED)),
        'recent_count': _safe_count(EmailDeliveryLog.objects.filter(created_at__gte=timezone.now() - timedelta(days=1))),
        'url': email_log_url,
        'failed_url': email_log_url + '?status__exact=failed' if email_log_url else '',
    }


def _build_download_summary(models):
    download_url = models.get(('lessons', 'lessonattachmentdownload'), {}).get('admin_url', '')
    return {
        'recent_count': _safe_count(
            LessonAttachmentDownload.objects.filter(downloaded_at__gte=timezone.now() - timedelta(days=1))
        ),
        'url': download_url,
    }


@register.simple_tag(takes_context=True)
def onedu_admin_dashboard(context):
    request = context.get('request')
    app_list = context.get('app_list') or context.get('available_apps') or []
    models = _model_map(app_list)
    return {
        'menu_sections': _build_menu(request, app_list, models),
        'stats': _build_stats(models),
        'pending_enrollments': _build_pending_enrollments(models),
        'active_watchers': _build_active_watchers(models),
        'quick_actions': _build_quick_actions(models),
        'courses': _build_courses(models),
        'recent_activity': _build_recent_activity(),
        'hls': _build_hls_summary(models),
        'access_logs': _build_access_log_summary(models),
        'email_logs': _build_email_summary(models),
        'downloads': _build_download_summary(models),
        'payment_pending_count': Enrollment.objects.filter(
            status=Enrollment.Status.REQUESTED,
            course__pricing_type=Course.PricingType.PAID,
            payment_status=Enrollment.PaymentStatus.PENDING,
        ).count(),
        'reenrollment_pending_count': ReEnrollmentRequest.objects.filter(
            status=ReEnrollmentRequest.Status.PENDING
        ).count(),
        'certificate_count': Certificate.objects.count(),
    }
