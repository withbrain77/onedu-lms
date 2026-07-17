from django.contrib import admin

from .models import ServerWarningAcknowledgement

admin.site.site_header = 'ONEDU LMS 관리자'
admin.site.site_title = 'ONEDU Admin'
admin.site.index_title = '운영 관리'


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
