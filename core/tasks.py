from celery import shared_task
from django.conf import settings
from django.core.management import call_command


@shared_task
def create_nonvideo_backup_task():
    if not settings.ONEDU_AUTOMATED_BACKUP_ENABLED:
        return 'disabled'

    call_command('create_nonvideo_backup')
    return 'created'
