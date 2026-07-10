from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Lesson


SERVER_VIDEO_FOLDER = 'lesson_videos'
VIDEO_FILE_EXTENSIONS = {'.mp4', '.m4v', '.mov', '.webm', '.ogg'}


def _private_media_root():
    return Path(settings.PRIVATE_MEDIA_ROOT).resolve()


def _server_video_root():
    return (_private_media_root() / SERVER_VIDEO_FOLDER).resolve()


def _format_file_size(size):
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} {unit}'
        value /= 1024
    return f'{size} B'


def list_server_video_files():
    root = _private_media_root()
    video_root = _server_video_root()
    if not video_root.exists():
        return []

    choices = []
    for path in video_root.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in VIDEO_FILE_EXTENSIONS:
            continue
        resolved_path = path.resolve()
        try:
            relative_path = resolved_path.relative_to(root)
        except ValueError:
            continue
        label = f'{relative_path.as_posix()} ({_format_file_size(path.stat().st_size)})'
        choices.append((relative_path.as_posix(), label))

    return sorted(choices, key=lambda item: item[0].lower())


def validate_server_video_file(value):
    if not value:
        return ''

    private_root = _private_media_root()
    video_root = _server_video_root()
    selected_path = (private_root / value).resolve()

    try:
        selected_path.relative_to(video_root)
    except ValueError as exc:
        raise ValidationError('lesson_videos 폴더 안의 영상 파일만 연결할 수 있습니다.') from exc

    if selected_path.suffix.lower() not in VIDEO_FILE_EXTENSIONS:
        raise ValidationError('MP4, M4V, MOV, WEBM, OGG 영상 파일만 연결할 수 있습니다.')

    if not selected_path.is_file():
        raise ValidationError('선택한 서버 영상 파일을 찾을 수 없습니다.')

    return selected_path.relative_to(private_root).as_posix()


class LessonAdminForm(forms.ModelForm):
    server_video_file = forms.ChoiceField(
        label='서버 영상 파일 연결',
        required=False,
        choices=(),
        help_text=(
            'NAS에 미리 업로드한 대용량 영상을 연결합니다. '
            '파일은 private_media/lesson_videos/ 아래에 있어야 하며, 선택해도 파일은 이동/복사되지 않습니다.'
        ),
    )

    class Meta:
        model = Lesson
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', '서버 파일을 연결하지 않음')] + list_server_video_files()
        self.fields['server_video_file'].choices = choices
        if self.instance and self.instance.video_file:
            self.fields['server_video_file'].initial = self.instance.video_file.name

    def clean_server_video_file(self):
        return validate_server_video_file(self.cleaned_data.get('server_video_file'))

    def save(self, commit=True):
        instance = super().save(commit=False)
        server_video_file = self.cleaned_data.get('server_video_file')
        if server_video_file:
            instance.video_file.name = server_video_file
        if commit:
            instance.save()
            self.save_m2m()
        return instance
