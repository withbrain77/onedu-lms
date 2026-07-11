from celery import shared_task
from django.utils import timezone

from .models import HLSConversionJob
from .services.hls import HLSConversionError, convert_lesson_to_hls


@shared_task(bind=True)
def convert_lesson_hls_task(self, job_id):
    job = HLSConversionJob.objects.select_related('lesson').get(pk=job_id)
    job.status = HLSConversionJob.Status.RUNNING
    job.progress_percent = 0
    job.progress_current_seconds = 0
    job.progress_total_seconds = job.lesson.duration_seconds or 0
    job.started_at = timezone.now()
    job.finished_at = None
    job.error_message = ''
    if self.request.id:
        job.celery_task_id = self.request.id
    job.save(
        update_fields=[
            'status',
            'progress_percent',
            'progress_current_seconds',
            'progress_total_seconds',
            'started_at',
            'finished_at',
            'error_message',
            'celery_task_id',
            'updated_at',
        ]
    )

    last_progress = {'percent': -1, 'seconds': -1}

    def save_progress(*, current_seconds, total_seconds, percent):
        percent = max(0, min(99, int(percent or 0)))
        current_seconds = max(0, int(current_seconds or 0))
        total_seconds = max(0, int(total_seconds or 0))
        if percent == last_progress['percent'] and current_seconds < last_progress['seconds'] + 5:
            return
        last_progress['percent'] = percent
        last_progress['seconds'] = current_seconds
        HLSConversionJob.objects.filter(pk=job.pk).update(
            progress_percent=percent,
            progress_current_seconds=current_seconds,
            progress_total_seconds=total_seconds,
            updated_at=timezone.now(),
        )

    try:
        convert_lesson_to_hls(
            job.lesson,
            force=job.force,
            hls_time=job.hls_time,
            transcode=job.transcode,
            progress_callback=save_progress,
        )
    except HLSConversionError as exc:
        job.status = HLSConversionJob.Status.FAILED
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])
        raise
    except Exception as exc:
        job.status = HLSConversionJob.Status.FAILED
        job.error_message = f'Unexpected error: {exc}'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])
        raise

    job.refresh_from_db(fields=['progress_current_seconds', 'progress_total_seconds'])
    job.status = HLSConversionJob.Status.SUCCEEDED
    job.progress_percent = 100
    job.progress_current_seconds = job.progress_total_seconds or job.lesson.duration_seconds or job.progress_current_seconds
    job.finished_at = timezone.now()
    job.error_message = ''
    job.save(
        update_fields=[
            'status',
            'progress_percent',
            'progress_current_seconds',
            'progress_total_seconds',
            'finished_at',
            'error_message',
            'updated_at',
        ]
    )
    return job.lesson.hls_playlist_path
