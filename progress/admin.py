from django.contrib import admin
from django.utils.html import format_html

from lessons.templatetags.lesson_time import duration_hms
from .models import WatchProgress


@admin.register(WatchProgress)
class WatchProgressAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'lesson',
        'enrollment',
        'progress_percent',
        'total_watched_display',
        'last_position_display',
        'is_completed',
        'last_watched_at',
    )
    list_filter = ('is_completed', 'lesson__course')
    search_fields = ('user__username', 'user__name', 'lesson__title', 'lesson__course__title')
    readonly_fields = (
        'total_watched_display',
        'last_position_display',
        'duration_display',
        'created_at',
        'updated_at',
        'last_watched_at',
    )
    fieldsets = (
        ('수강 정보', {'fields': ('user', 'enrollment', 'lesson')}),
        (
            '시청 분석',
            {
                'fields': (
                    'progress_percent',
                    'duration_display',
                    'total_watched_display',
                    'last_position_display',
                    'is_completed',
                    'completed_at',
                )
            },
        ),
        (
            '원본 기록',
            {
                'classes': ('collapse',),
                'fields': ('duration_seconds', 'total_watched_seconds', 'last_position_seconds'),
            },
        ),
        ('기록', {'fields': ('last_watched_at', 'created_at', 'updated_at')}),
    )
    list_select_related = ('user', 'lesson', 'lesson__course', 'enrollment')

    @admin.display(description='영상 길이', ordering='duration_seconds')
    def duration_display(self, obj):
        duration = self._duration_seconds(obj)
        if not duration:
            return '-'
        return duration_hms(duration)

    @admin.display(description='총 시청 시간', ordering='total_watched_seconds')
    def total_watched_display(self, obj):
        watched = obj.total_watched_seconds or 0
        multiplier = self._watch_multiplier(obj)
        if multiplier is None:
            return format_html('{}<br><span style="color:#64748b;">(영상 길이 없음)</span>', duration_hms(watched))
        multiplier_label = f'{multiplier:.1f}'
        return format_html(
            '{}<br><span style="color:#64748b;">({}배)</span>',
            duration_hms(watched),
            multiplier_label,
        )

    @admin.display(description='마지막 시청 위치', ordering='last_position_seconds')
    def last_position_display(self, obj):
        return duration_hms(obj.last_position_seconds)

    def _duration_seconds(self, obj):
        return obj.duration_seconds or getattr(obj.lesson, 'duration_seconds', 0) or 0

    def _watch_multiplier(self, obj):
        duration = self._duration_seconds(obj)
        if not duration:
            return None
        return (obj.total_watched_seconds or 0) / duration
