from django.contrib import admin

from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'duration_seconds', 'is_public', 'updated_at')
    list_filter = ('is_public', 'course')
    search_fields = ('title', 'description', 'course__title')
    list_editable = ('order', 'is_public')
    ordering = ('course', 'order')
    list_select_related = ('course',)
    list_per_page = 50
