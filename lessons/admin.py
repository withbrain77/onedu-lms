from django.contrib import admin

from .forms import LessonAdminForm
from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonAdminForm
    list_display = (
        'title',
        'course',
        'order',
        'video_status',
        'duration_seconds',
        'is_public',
        'updated_at',
    )
    list_filter = ('is_public', 'course')
    search_fields = ('title', 'description', 'course__title')
    list_editable = ('order', 'is_public')
    ordering = ('course', 'order')
    list_select_related = ('course',)
    list_per_page = 50
    fieldsets = (
        ('기본 정보', {'fields': ('course', 'title', 'description')}),
        ('영상', {'fields': ('video_file', 'server_video_file', 'duration_seconds')}),
        ('운영', {'fields': ('order', 'is_public')}),
    )

    @admin.display(description='영상')
    def video_status(self, obj):
        return obj.video_file.name if obj.video_file else '없음'
