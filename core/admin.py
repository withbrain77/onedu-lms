from django.contrib import admin

from .models import Notice, ServerWarningAcknowledgement

admin.site.site_header = 'ONEDU LMS 관리자'
admin.site.site_title = 'ONEDU Admin'
admin.site.index_title = '운영 관리'


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'scope', 'is_pinned', 'is_published', 'published_at', 'updated_at')
    list_filter = ('is_published', 'is_pinned', 'course', 'published_at')
    search_fields = ('title', 'content', 'course__title')
    autocomplete_fields = ('course',)
    date_hierarchy = 'published_at'
    ordering = ('-is_pinned', '-published_at')
    list_per_page = 50

    @admin.display(description='대상')
    def scope(self, obj):
        return obj.scope_label


@admin.register(ServerWarningAcknowledgement)
class ServerWarningAcknowledgementAdmin(admin.ModelAdmin):
    list_display = ('acknowledged_at', 'warning_key', 'acknowledged_by', 'message')
    list_filter = ('acknowledged_at', 'warning_key')
    search_fields = ('warning_key', 'message', 'acknowledged_by__username', 'acknowledged_by__name')
    readonly_fields = ('warning_key', 'message_hash', 'message', 'acknowledged_by', 'acknowledged_at')
    ordering = ('-acknowledged_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
