from django.contrib import admin

from .models import WatchProgress


@admin.register(WatchProgress)
class WatchProgressAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'lesson',
        'enrollment',
        'progress_percent',
        'total_watched_seconds',
        'last_position_seconds',
        'is_completed',
        'last_watched_at',
    )
    list_filter = ('is_completed', 'lesson__course')
    search_fields = ('user__username', 'user__name', 'lesson__title', 'lesson__course__title')
    readonly_fields = ('created_at', 'updated_at', 'last_watched_at')
