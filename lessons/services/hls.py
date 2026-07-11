import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone


class HLSConversionError(Exception):
    pass


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


def get_lesson_video_path(lesson):
    if not lesson.video_file:
        return None

    private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    source_path = (private_root / lesson.video_file.name).resolve()
    try:
        source_path.relative_to(private_root)
    except ValueError:
        return None
    if not source_path.is_file():
        return None
    return source_path


def refresh_lesson_duration_seconds(lesson, *, force=False):
    if lesson.duration_seconds and not force:
        return lesson.duration_seconds

    source_path = get_lesson_video_path(lesson)
    if not source_path:
        return 0

    duration_seconds = probe_video_duration_seconds(source_path)
    if duration_seconds:
        lesson.duration_seconds = duration_seconds
        lesson.save(update_fields=['duration_seconds', 'updated_at'])
    return duration_seconds


def parse_ffmpeg_progress_seconds(line):
    if not line.startswith('out_time_ms='):
        return None
    try:
        return max(0, int(int(line.split('=', 1)[1]) / 1_000_000))
    except (TypeError, ValueError):
        return None


def run_ffmpeg(command, *, progress_callback=None, total_seconds=0):
    if not progress_callback:
        subprocess.run(command, check=True)
        return

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    assert process.stdout is not None
    for line in process.stdout:
        current_seconds = parse_ffmpeg_progress_seconds(line.strip())
        if current_seconds is None:
            continue
        percent = 0
        if total_seconds:
            percent = min(99, int((current_seconds / total_seconds) * 100))
        progress_callback(
            current_seconds=current_seconds,
            total_seconds=total_seconds,
            percent=percent,
        )

    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def clear_lesson_hls_state(lesson):
    lesson.hls_playlist_path = ''
    lesson.hls_ready = False
    lesson.hls_converted_at = None
    lesson.save(update_fields=['hls_playlist_path', 'hls_ready', 'hls_converted_at', 'updated_at'])


def convert_lesson_to_hls(lesson, *, force=False, hls_time=6, transcode=False, write=None, progress_callback=None):
    if not lesson.video_file:
        raise HLSConversionError('Lesson has no video_file to convert.')

    log = write or (lambda message: None)
    private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    source_path = (private_root / lesson.video_file.name).resolve()
    try:
        source_path.relative_to(private_root)
    except ValueError as exc:
        raise HLSConversionError('Lesson video file must be inside PRIVATE_MEDIA_ROOT.') from exc
    if not source_path.is_file():
        raise HLSConversionError(f'Video file does not exist: {source_path}')

    output_root = (private_root / 'lesson_hls').resolve()
    output_dir = (output_root / f'lesson-{lesson.pk}').resolve()
    try:
        output_dir.relative_to(output_root)
    except ValueError as exc:
        raise HLSConversionError('Invalid HLS output directory.') from exc

    playlist_path = output_dir / 'index.m3u8'
    if output_dir.exists():
        if not force:
            raise HLSConversionError('HLS output already exists. Use force to overwrite it.')
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    segment_pattern = output_dir / 'segment_%05d.ts'
    total_seconds = lesson.duration_seconds or refresh_lesson_duration_seconds(lesson)
    if progress_callback:
        progress_callback(current_seconds=0, total_seconds=total_seconds, percent=0)

    command = [
        'ffmpeg',
        '-y',
        '-nostdin',
        '-hide_banner',
    ]
    if progress_callback:
        command += ['-progress', 'pipe:1', '-nostats']
    command += [
        '-i',
        str(source_path),
        '-map',
        '0:v:0',
        '-map',
        '0:a:0?',
    ]
    if transcode:
        command += [
            '-c:v',
            'libx264',
            '-preset',
            'veryfast',
            '-crf',
            '23',
            '-c:a',
            'aac',
            '-b:a',
            '128k',
        ]
    else:
        command += ['-c', 'copy']

    command += [
        '-start_number',
        '0',
        '-hls_time',
        str(hls_time),
        '-hls_playlist_type',
        'vod',
        '-hls_segment_filename',
        str(segment_pattern),
        str(playlist_path),
    ]

    log(f'Converting lesson {lesson.pk}: {lesson.title}')
    log(f'Source: {source_path}')
    log(f'Output: {playlist_path}')
    try:
        run_ffmpeg(command, progress_callback=progress_callback, total_seconds=total_seconds)
    except FileNotFoundError as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        clear_lesson_hls_state(lesson)
        raise HLSConversionError('ffmpeg is not installed or not available in PATH.') from exc
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        clear_lesson_hls_state(lesson)
        raise HLSConversionError(f'ffmpeg failed with exit code {exc.returncode}.') from exc

    if not playlist_path.is_file():
        clear_lesson_hls_state(lesson)
        raise HLSConversionError('ffmpeg finished but index.m3u8 was not created.')

    lesson.hls_playlist_path = playlist_path.relative_to(private_root).as_posix()
    lesson.hls_ready = True
    lesson.hls_converted_at = timezone.now()
    lesson.save(update_fields=['hls_playlist_path', 'hls_ready', 'hls_converted_at', 'updated_at'])

    return lesson.hls_playlist_path
