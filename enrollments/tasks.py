from celery import shared_task
from django.core.management import call_command


@shared_task
def send_expiry_notices_task():
    call_command('send_expiry_notices')
    return True
