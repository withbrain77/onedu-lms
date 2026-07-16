from django.contrib import admin
from django.contrib import messages
from django.conf import settings
from django.shortcuts import redirect
from django.urls import path, reverse

from .forms import LessonAdminForm
from .models import HLSConversionJob, Lesson, LessonAttachment, LessonAttachmentDownload
from .services.hls import refresh_lesson_duration_seconds
from .tasks import convert_lesson_hls_task
from .templatetags.lesson_time import duration_hms


ACTIVE_HLS_JOB_STATUSES = (
    HLSConversionJob.Status.PENDING,
    HLSConversionJob.Status.RUNNING,
)


class LessonAttachmentInline(admin.TabularInline):
    model = LessonAttachment
    extra = 0
    fields = ('order', 'title', 'file', 'description', 'is_public')
    ordering = ('order', 'id')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonAdminForm
    change_form_template = 'admin/lessons/lesson/change_form.html'
    inlines = (LessonAttachmentInline,)
    list_display = (
        'title',
        'course',
        'order',
        'video_status',
        'hls_status',
        'latest_hls_job_status',
        'duration_display',
        'is_public',
        'updated_at',
    )
    list_filter = ('is_public', 'course', 'hls_ready')
    search_fields = ('title', 'description', 'course__title')
    list_editable = ('order', 'is_public')
    ordering = ('course', 'order')
    list_select_related = ('course',)
    list_per_page = 50
    readonly_fields = ('hls_converted_at',)
    actions = ('refresh_duration_seconds', 'queue_hls_conversion', 'queue_hls_reconversion')
    fieldsets = (
        ('기본 정보', {'fields': ('course', 'title', 'description')}),
        ('영상', {'fields': ('video_file', 'server_video_file', 'duration_seconds')}),
        (
            'HLS 스트리밍',
            {
                'fields': ('hls_ready', 'hls_playlist_path', 'hls_converted_at'),
                'description': '대용량 영상은 관리자 버튼으로 HLS 변환 작업을 큐에 등록하면 worker가 뒤에서 변환합니다.',
            },
        ),
        ('운영', {'fields': ('order', 'is_public')}),
    )

    @admin.display(description='영상')
    def video_status(self, obj):
        return obj.video_file.name if obj.video_file else '없음'

    @admin.display(description='영상 길이', ordering='duration_seconds')
    def duration_display(self, obj):
        if not obj.duration_seconds:
            return '미확인'
        return duration_hms(obj.duration_seconds)

    @admin.display(description='HLS')
    def hls_status(self, obj):
        return '준비됨' if obj.has_hls else '없음'

    @admin.display(description='최근 변환 작업')
    def latest_hls_job_status(self, obj):
        job = obj.hls_jobs.order_by('-created_at').first()
        if not job:
            return '없음'
        if job.status == HLSConversionJob.Status.RUNNING:
            return f'{job.get_status_display()} {job.progress_percent}%'
        if job.status == HLSConversionJob.Status.SUCCEEDED:
            return '완료 100%'
        return job.get_status_display()

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/queue-hls/',
                self.admin_site.admin_view(self.queue_hls_view),
                name='lessons_lesson_queue_hls',
            ),
        ]
        return custom_urls + super().get_urls()

    def queue_hls_view(self, request, object_id):
        lesson = self.get_object(request, object_id)
        if not lesson:
            self.message_user(request, '차시를 찾을 수 없습니다.', messages.ERROR)
            return redirect(reverse('admin:lessons_lesson_changelist'))
        if request.method != 'POST':
            self.message_user(request, 'HLS 변환 요청은 버튼으로 실행해야 합니다.', messages.WARNING)
            return redirect(reverse('admin:lessons_lesson_change', args=[object_id]))

        force = request.POST.get('force') == '1'
        transcode = request.POST.get('transcode') == '1'
        self._queue_lesson_hls_conversion(request, lesson, force=force, transcode=transcode)
        return redirect(reverse('admin:lessons_lesson_change', args=[object_id]))

    @admin.action(description='선택한 차시 HLS 변환 요청')
    def queue_hls_conversion(self, request, queryset):
        queued_count = 0
        for lesson in queryset:
            queued_count += int(
                self._queue_lesson_hls_conversion(request, lesson, force=False, transcode=False, emit_success=False)
            )
        if queued_count:
            self.message_user(request, f'{queued_count}개 차시의 HLS 변환 작업을 큐에 등록했습니다.', messages.SUCCESS)

    @admin.action(description='선택한 차시 HLS 재변환 요청(기존 결과 덮어쓰기)')
    def queue_hls_reconversion(self, request, queryset):
        queued_count = 0
        for lesson in queryset:
            queued_count += int(
                self._queue_lesson_hls_conversion(request, lesson, force=True, transcode=False, emit_success=False)
            )
        if queued_count:
            self.message_user(request, f'{queued_count}개 차시의 HLS 재변환 작업을 큐에 등록했습니다.', messages.SUCCESS)

    @admin.action(description='선택한 차시 영상 길이 갱신')
    def refresh_duration_seconds(self, request, queryset):
        updated_count = 0
        skipped_count = 0
        for lesson in queryset:
            duration_seconds = refresh_lesson_duration_seconds(lesson, force=True)
            if duration_seconds:
                updated_count += 1
            else:
                skipped_count += 1
        if updated_count:
            self.message_user(request, f'{updated_count}개 차시의 영상 길이를 갱신했습니다.', messages.SUCCESS)
        if skipped_count:
            self.message_user(request, f'{skipped_count}개 차시는 영상 파일을 찾지 못했거나 길이를 읽지 못했습니다.', messages.WARNING)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.video_file:
            return

        should_refresh = (
            not obj.duration_seconds
            or 'video_file' in form.changed_data
            or 'server_video_file' in form.changed_data
        )
        if not should_refresh:
            return

        duration_seconds = refresh_lesson_duration_seconds(
            obj,
            force='video_file' in form.changed_data or 'server_video_file' in form.changed_data,
        )
        if duration_seconds:
            self.message_user(request, f'영상 길이를 {duration_hms(duration_seconds)}로 갱신했습니다.', messages.SUCCESS)

    def _queue_lesson_hls_conversion(self, request, lesson, *, force=False, transcode=False, emit_success=True):
        if not lesson.video_file:
            self.message_user(request, f'"{lesson}" 차시에 연결된 영상 파일이 없습니다.', messages.WARNING)
            return False
        if lesson.hls_jobs.filter(status__in=ACTIVE_HLS_JOB_STATUSES).exists():
            self.message_user(request, f'"{lesson}" 차시는 이미 변환 작업이 대기/진행 중입니다.', messages.WARNING)
            return False

        job = HLSConversionJob.objects.create(
            lesson=lesson,
            requested_by=request.user if request.user.is_authenticated else None,
            force=force,
            transcode=transcode,
        )
        try:
            async_result = convert_lesson_hls_task.apply_async(
                args=(job.pk,),
                queue=settings.CELERY_VIDEO_QUEUE,
            )
            if not async_result.id:
                raise RuntimeError('Celery returned an empty task id.')
        except Exception as exc:
            job.status = HLSConversionJob.Status.FAILED
            job.error_message = f'작업 큐 등록 실패: {exc}'
            job.save(update_fields=['status', 'error_message', 'updated_at'])
            self.message_user(request, f'HLS 변환 작업을 큐에 등록하지 못했습니다: {exc}', messages.ERROR)
            return False

        job.celery_task_id = async_result.id or ''
        job.save(update_fields=['celery_task_id', 'updated_at'])
        if emit_success:
            self.message_user(request, f'"{lesson}" HLS 변환 작업을 등록했습니다.', messages.SUCCESS)
        return True


@admin.register(LessonAttachment)
class LessonAttachmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'course_title', 'order', 'is_public', 'updated_at')
    list_filter = ('is_public', 'lesson__course')
    search_fields = ('title', 'description', 'lesson__title', 'lesson__course__title')
    list_editable = ('order', 'is_public')
    list_select_related = ('lesson', 'lesson__course')
    ordering = ('lesson__course', 'lesson__order', 'order')
    list_per_page = 50

    @admin.display(description='강의', ordering='lesson__course__title')
    def course_title(self, obj):
        return obj.lesson.course.title


@admin.register(LessonAttachmentDownload)
class LessonAttachmentDownloadAdmin(admin.ModelAdmin):
    list_display = (
        'downloaded_at',
        'user',
        'attachment_title',
        'filename',
        'course',
        'lesson',
        'ip_address',
        'device_summary',
    )
    list_filter = ('course', 'lesson', 'downloaded_at')
    search_fields = (
        'user__username',
        'user__name',
        'user__email',
        'attachment_title',
        'filename',
        'course__title',
        'lesson__title',
        'ip_address',
        'device_summary',
        'user_agent',
    )
    readonly_fields = (
        'user',
        'attachment',
        'lesson',
        'course',
        'attachment_title',
        'filename',
        'ip_address',
        'device_summary',
        'user_agent',
        'downloaded_at',
    )
    fieldsets = (
        ('다운로드 정보', {'fields': ('downloaded_at', 'user', 'attachment', 'attachment_title', 'filename')}),
        ('학습 대상', {'fields': ('course', 'lesson')}),
        ('접속 환경', {'fields': ('ip_address', 'device_summary', 'user_agent')}),
    )
    date_hierarchy = 'downloaded_at'
    ordering = ('-downloaded_at',)
    list_select_related = ('user', 'attachment', 'lesson', 'course')
    list_per_page = 50

    def has_add_permission(self, request):
        return False


@admin.register(HLSConversionJob)
class HLSConversionJobAdmin(admin.ModelAdmin):
    list_display = (
        'lesson',
        'status',
        'progress_display',
        'requested_by',
        'force',
        'transcode',
        'hls_time',
        'created_at',
        'started_at',
        'finished_at',
    )
    list_filter = ('status', 'force', 'transcode', 'created_at')
    search_fields = ('lesson__title', 'lesson__course__title', 'requested_by__username', 'celery_task_id')
    readonly_fields = (
        'lesson',
        'requested_by',
        'status',
        'force',
        'transcode',
        'hls_time',
        'progress_percent',
        'progress_current_seconds',
        'progress_total_seconds',
        'celery_task_id',
        'error_message',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
    )
    list_select_related = ('lesson', 'lesson__course', 'requested_by')
    ordering = ('-created_at',)

    @admin.display(description='진행률', ordering='progress_percent')
    def progress_display(self, obj):
        if obj.status == HLSConversionJob.Status.SUCCEEDED:
            return '100%'
        if obj.progress_total_seconds:
            return (
                f'{obj.progress_percent}% '
                f'({duration_hms(obj.progress_current_seconds)} / {duration_hms(obj.progress_total_seconds)})'
            )
        if obj.progress_current_seconds:
            return f'{duration_hms(obj.progress_current_seconds)} 처리'
        return f'{obj.progress_percent}%'
