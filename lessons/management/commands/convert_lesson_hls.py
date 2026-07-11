from django.core.management.base import BaseCommand, CommandError

from lessons.models import Lesson
from lessons.services.hls import HLSConversionError, convert_lesson_to_hls


class Command(BaseCommand):
    help = 'Convert a lesson video file into HLS files under PRIVATE_MEDIA_ROOT.'

    def add_arguments(self, parser):
        parser.add_argument('lesson_id', type=int)
        parser.add_argument('--force', action='store_true', help='Overwrite existing HLS files for this lesson.')
        parser.add_argument('--hls-time', type=int, default=6, help='Segment length in seconds. Default: 6.')
        parser.add_argument(
            '--transcode',
            action='store_true',
            help='Transcode to H.264/AAC instead of stream-copying the source video.',
        )

    def handle(self, *args, **options):
        lesson = Lesson.objects.select_related('course').filter(pk=options['lesson_id']).first()
        if not lesson:
            raise CommandError(f'Lesson {options["lesson_id"]} does not exist.')
        try:
            playlist_path = convert_lesson_to_hls(
                lesson,
                force=options['force'],
                hls_time=options['hls_time'],
                transcode=options['transcode'],
                write=self.stdout.write,
            )
        except HLSConversionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'HLS ready: {playlist_path}'))
