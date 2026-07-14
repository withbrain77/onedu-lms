import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Enrollment

logger = logging.getLogger(__name__)


def _notification_recipients():
    recipients = getattr(settings, 'ONEDU_ADMIN_NOTIFICATION_EMAILS', [])
    if isinstance(recipients, str):
        recipients = [item.strip() for item in recipients.split(',') if item.strip()]
    recipients = list(recipients)
    if recipients:
        return recipients

    email_host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    return [email_host_user] if email_host_user else []


def _admin_change_url(enrollment):
    path = reverse('admin:enrollments_enrollment_change', args=[enrollment.pk])
    return _site_url(path)


def _site_url(path):
    public_site_url = getattr(settings, 'PUBLIC_SITE_URL', '')
    if public_site_url:
        return f'{public_site_url}{path}'
    return path


def _price_label(course):
    if course.is_free:
        return '무료'
    return f'{course.price_krw:,}원'


def notify_enrollment_request(enrollment):
    if not getattr(settings, 'ONEDU_NOTIFY_ENROLLMENT_REQUEST', True):
        return False
    if enrollment.status != Enrollment.Status.REQUESTED:
        return False
    if enrollment.course.is_free:
        return False

    recipients = _notification_recipients()
    if not recipients:
        logger.warning('Enrollment request notification skipped because no admin recipient email is configured.')
        return False

    requested_at = timezone.localtime(enrollment.created_at).strftime('%Y-%m-%d %H:%M')
    admin_url = _admin_change_url(enrollment)
    user = enrollment.user
    course = enrollment.course

    subject = '[ONEDU] 새 수강 신청이 접수되었습니다'
    message = (
        '새 수강 신청이 접수되었습니다.\n\n'
        f'수강생: {user.display_name} ({user.username})\n'
        f'이메일: {user.email or "-"}\n'
        f'강의: {course.title}\n'
        f'이용료: {_price_label(course)}\n'
        f'신청일시: {requested_at}\n\n'
        f'관리자에서 확인하기:\n{admin_url}\n'
    )

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send enrollment request notification email.')
        return False

    return True


def notify_enrollment_approved(enrollment):
    if not getattr(settings, 'ONEDU_NOTIFY_ENROLLMENT_APPROVAL', True):
        return False
    if enrollment.status != Enrollment.Status.APPROVED:
        return False

    recipient = (enrollment.user.email or '').strip()
    if not recipient:
        logger.warning(
            'Enrollment approval notification skipped because student %s has no email address.',
            enrollment.user_id,
        )
        return False

    course_url = _site_url(reverse('enrollments:course_detail', kwargs={'course_id': enrollment.course_id}))
    classroom_url = _site_url(reverse('enrollments:classroom'))
    user = enrollment.user
    course = enrollment.course
    approved_at = timezone.localtime(enrollment.approved_at or timezone.now()).strftime('%Y-%m-%d %H:%M')
    if enrollment.start_date and enrollment.end_date:
        period = f'{enrollment.start_date} ~ {enrollment.end_date}'
    else:
        period = '관리자가 별도로 안내하거나 추후 배정'

    subject = '[ONEDU] 수강 신청이 승인되었습니다'
    message = (
        f'안녕하세요, {user.display_name}님.\n\n'
        '수강 신청이 승인되었습니다.\n\n'
        f'강의: {course.title}\n'
        f'수강 기간: {period}\n'
        f'승인일시: {approved_at}\n\n'
        '아래 링크에서 학습을 시작할 수 있습니다.\n'
        f'강의 바로가기: {course_url}\n'
        f'내 강의실: {classroom_url}\n\n'
        '수강 기간 안에서 영상을 시청해 주세요.\n'
    )

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send enrollment approval notification email.')
        return False

    return True
