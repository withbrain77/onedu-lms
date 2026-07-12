from django.contrib import admin
from django.db.models import Count

from lessons.forms import LessonAdminForm
from lessons.models import Lesson

from .models import Course


class LessonInline(admin.TabularInline):
    model = Lesson
    form = LessonAdminForm
    extra = 0
    fields = (
        'order',
        'title',
        'video_file',
        'server_video_file',
        'duration_seconds',
        'hls_ready',
        'hls_job_status',
        'hls_playlist_path',
        'is_public',
    )
    readonly_fields = ('hls_ready', 'hls_job_status', 'hls_playlist_path')
    ordering = ('order',)
    show_change_link = True

    @admin.display(description='HLS 작업')
    def hls_job_status(self, obj):
        if not obj.pk:
            return '-'
        job = obj.hls_jobs.order_by('-created_at').first()
        return job.get_status_display() if job else '없음'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'is_public',
        'pricing_type',
        'price_display',
        'default_enrollment_days',
        'required_progress_percent',
        'require_quiz_pass',
        'certificate_enabled',
        'lesson_count',
        'enrollment_count',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_public', 'pricing_type', 'require_quiz_pass', 'certificate_enabled', 'created_at')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LessonInline]
    list_per_page = 30
    fieldsets = (
        ('기본 정보', {'fields': ('title', 'slug', 'description', 'thumbnail', 'is_public')}),
        ('참가비/승인 정책', {'fields': ('pricing_type', 'price_krw', 'default_enrollment_days')}),
        ('수료 정책', {'fields': ('required_progress_percent', 'require_quiz_pass', 'certificate_enabled')}),
        ('기록', {'fields': ('created_by',)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(admin_enrollment_count=Count('enrollments'))

    @admin.display(description='수강 신청 수', ordering='admin_enrollment_count')
    def enrollment_count(self, obj):
        return obj.admin_enrollment_count

    @admin.display(description='참가비', ordering='price_krw')
    def price_display(self, obj):
        return obj.price_label

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
