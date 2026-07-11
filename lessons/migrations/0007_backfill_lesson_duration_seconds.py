from pathlib import Path
import subprocess

from django.conf import settings
from django.db import migrations


def probe_video_duration_seconds(source_path):
    command = [
        'ffprobe',
        '-v',
        'error',
        '-show_entries',
        'format=duration',
        '-of',
        'default=noprint_wrappers=1:nokey=1',
        str(source_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return 0

    try:
        return max(0, int(float(result.stdout.strip())))
    except (TypeError, ValueError):
        return 0


def backfill_lesson_duration_seconds(apps, schema_editor):
    Lesson = apps.get_model('lessons', 'Lesson')
    private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()

    lessons = Lesson.objects.exclude(video_file='').filter(duration_seconds=0)
    for lesson in lessons:
        source_path = (private_root / lesson.video_file.name).resolve()
        try:
            source_path.relative_to(private_root)
        except ValueError:
            continue
        if not source_path.is_file():
            continue

        duration_seconds = probe_video_duration_seconds(source_path)
        if duration_seconds:
            lesson.duration_seconds = duration_seconds
            lesson.save(update_fields=['duration_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0006_hlsconversionjob_progress_current_seconds_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_lesson_duration_seconds, migrations.RunPython.noop),
    ]
