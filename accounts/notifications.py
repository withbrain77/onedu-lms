import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from enrollments.models import EmailDeliveryLog
from enrollments.notifications import deliver_or_queue_email, record_email_delivery_log

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


def _site_url(path):
    public_site_url = getattr(settings, 'PUBLIC_SITE_URL', '')
    if public_site_url:
        return f'{public_site_url}{path}'
    return path


def notify_account_withdrawal_request(withdrawal_request):
    if not getattr(settings, 'ONEDU_NOTIFY_ACCOUNT_WITHDRAWAL_REQUEST', True):
        return False

    user = withdrawal_request.user
    recipients = _notification_recipients()
    subject = '[ONEDU] 계정 탈퇴 요청이 접수되었습니다'
    if not recipients:
        logger.warning('Account withdrawal notification skipped because no admin recipient email is configured.')
        record_email_delivery_log(
            EmailDeliveryLog.Kind.ACCOUNT_WITHDRAWAL_REQUEST,
            [],
            subject,
            EmailDeliveryLog.Status.SKIPPED,
            '관리자 알림 수신자 이메일이 설정되어 있지 않습니다.',
            user=user,
        )
        return False

    requested_at = timezone.localtime(withdrawal_request.requested_at).strftime('%Y-%m-%d %H:%M')
    admin_url = _site_url(reverse('admin:accounts_accountwithdrawalrequest_change', args=[withdrawal_request.pk]))
    user_label = withdrawal_request.name_snapshot or (user.display_name if user else '-')
    username = withdrawal_request.username_snapshot or (user.username if user else '-')
    email = withdrawal_request.email_snapshot or (user.email if user else '-')

    message = (
        '계정 탈퇴 요청이 접수되었습니다.\n\n'
        f'사용자: {user_label} ({username})\n'
        f'이메일: {email or "-"}\n'
        f'요청일시: {requested_at}\n\n'
        '요청 사유와 수강 이력은 관리자 화면에서 확인해 주세요.\n'
        f'관리자에서 확인하기:\n{admin_url}\n'
    )

    return deliver_or_queue_email(
        EmailDeliveryLog.Kind.ACCOUNT_WITHDRAWAL_REQUEST,
        recipients,
        subject,
        message,
        user=user,
    )
