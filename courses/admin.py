from django.contrib import admin
from django.db.models import Count

from lessons.forms import LessonAdminForm
from lessons.models import Lesson

from .models import Course


class LessonInline(admin.TabularInline):
    model = Lesson
    form = LessonAdminForm
    extra = 0
    fields = ('order', 'title', 'video_file', 'server_video_file', 'duration_seconds', 'is_public')
    ordering = ('order',)
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'is_public',
        'required_progress_percent',
        'require_quiz_pass',
        'certificate_enabled',
        'lesson_count',
        'enrollment_count',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_public', 'require_quiz_pass', 'certificate_enabled', 'created_at')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LessonInline]
    list_per_page = 30
    fieldsets = (
        ('기본 정보', {'fields': ('title', 'slug', 'description', 'thumbnail', 'is_public')}),
        ('수료 정책', {'fields': ('required_progress_percent', 'require_quiz_pass', 'certificate_enabled')}),
        ('기록', {'fields': ('created_by',)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(admin_enrollment_count=Count('enrollments'))

    @admin.display(description='수강 신청 수', ordering='admin_enrollment_count')
    def enrollment_count(self, obj):
        return obj.admin_enrollment_count

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
