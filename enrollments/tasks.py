from celery import shared_task
from django.core.management import call_command


@shared_task
def send_expiry_notices_task():
    call_command('send_expiry_notices')
    return True


@shared_task
def send_queued_email_task(log_id, subject, message, recipients):
    from .notifications import send_queued_email_log

    return send_queued_email_log(log_id, subject, message, recipients)
