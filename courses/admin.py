from django.contrib import admin
from django.db.models import Count

from lessons.forms import LessonAdminForm
from lessons.models import Lesson
from lessons.templatetags.lesson_time import duration_hms

from .models import Course, CourseInvitation


class LessonInline(admin.TabularInline):
    model = Lesson
    form = LessonAdminForm
    extra = 0
    fields = (
        'order',
        'title',
        'video_file',
        'server_video_file',
        'duration_display',
        'hls_ready',
        'hls_job_status',
        'hls_playlist_path',
        'is_public',
    )
    readonly_fields = ('duration_display', 'hls_ready', 'hls_job_status', 'hls_playlist_path')
    ordering = ('order',)
    show_change_link = True

    @admin.display(description='영상 길이')
    def duration_display(self, obj):
        if not obj.pk:
            return '-'
        if not obj.duration_seconds:
            return '미확인'
        return duration_hms(obj.duration_seconds)

    @admin.display(description='HLS 작업')
    def hls_job_status(self, obj):
        if not obj.pk:
            return '-'
        job = obj.hls_jobs.order_by('-created_at').first()
        return job.get_status_display() if job else '없음'


class CourseInvitationInline(admin.TabularInline):
    model = CourseInvitation
    extra = 0
    fields = ('user', 'active', 'note', 'invited_by', 'created_at')
    readonly_fields = ('invited_by', 'created_at')
    autocomplete_fields = ('user',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'is_public',
        'visibility',
        'pricing_type',
        'price_display',
        'default_enrollment_days',
        'required_progress_percent',
        'require_quiz_pass',
        'certificate_enabled',
        'lesson_count',
        'invitation_count',
        'enrollment_count',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_public', 'visibility', 'pricing_type', 'require_quiz_pass', 'certificate_enabled', 'created_at')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CourseInvitationInline, LessonInline]
    list_per_page = 30
    fieldsets = (
        ('기본 정보', {'fields': ('title', 'slug', 'description', 'thumbnail', 'is_public', 'visibility')}),
        ('이용료/승인 정책', {'fields': ('pricing_type', 'price_krw', 'default_enrollment_days')}),
        ('수료 정책', {'fields': ('required_progress_percent', 'require_quiz_pass', 'certificate_enabled')}),
        ('기록', {'fields': ('created_by',)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            admin_enrollment_count=Count('enrollments', distinct=True),
            admin_invitation_count=Count('invitations', distinct=True),
        )

    @admin.display(description='수강 신청 수', ordering='admin_enrollment_count')
    def enrollment_count(self, obj):
        return obj.admin_enrollment_count

    @admin.display(description='초대 회원 수', ordering='admin_invitation_count')
    def invitation_count(self, obj):
        return obj.admin_invitation_count

    @admin.display(description='이용료', ordering='price_krw')
    def price_display(self, obj):
        return obj.price_label

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for obj in instances:
            if isinstance(obj, CourseInvitation) and not obj.invited_by_id:
                obj.invited_by = request.user
            obj.save()
        formset.save_m2m()


@admin.register(CourseInvitation)
class CourseInvitationAdmin(admin.ModelAdmin):
    list_display = ('course', 'user', 'active', 'invited_by', 'created_at')
    list_filter = ('active', 'course', 'created_at')
    search_fields = ('course__title', 'user__username', 'user__name', 'user__email', 'note')
    autocomplete_fields = ('course', 'user')
    readonly_fields = ('created_at',)
