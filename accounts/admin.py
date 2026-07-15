from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import AccessLog, User
from .reports import build_student_learning_report


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'display_name_column',
        'email',
        'role',
        'is_active',
        'is_staff',
        'last_login',
        'learning_report_link',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'name', 'email', 'phone')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('LMS 정보', {'fields': ('name', 'phone', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('LMS 정보', {'fields': ('name', 'phone', 'role')}),
    )

    @admin.display(description='이름')
    def display_name_column(self, obj):
        return obj.display_name

    @admin.display(description='학습 리포트')
    def learning_report_link(self, obj):
        if not obj.pk:
            return '-'
        url = reverse('admin:accounts_user_learning_report', args=[obj.pk])
        return format_html('<a class="button" href="{}">보기</a>', url)

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/learning-report/',
                self.admin_site.admin_view(self.learning_report_view),
                name='accounts_user_learning_report',
            ),
        ]
        return custom_urls + super().get_urls()

    def learning_report_view(self, request, object_id):
        student = get_object_or_404(User, pk=object_id)
        context = {
            **self.admin_site.each_context(request),
            'title': f'{student.display_name} 학습 리포트',
            'opts': self.model._meta,
            'student': student,
            'report': build_student_learning_report(student),
        }
        return render(request, 'admin/accounts/user/learning_report.html', context)


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'user',
        'event_type',
        'ip_address',
        'device_summary',
        'course_title',
        'lesson_title',
        'is_suspicious',
        'short_reason',
    )
    list_filter = ('event_type', 'is_suspicious', 'created_at')
    search_fields = (
        'user__username',
        'user__name',
        'user__email',
        'ip_address',
        'device_summary',
        'user_agent',
        'course_title',
        'lesson_title',
        'path',
        'suspicious_reason',
    )
    readonly_fields = (
        'user',
        'event_type',
        'ip_address',
        'user_agent',
        'device_summary',
        'session_key',
        'path',
        'course_id_value',
        'course_title',
        'lesson_id_value',
        'lesson_title',
        'is_suspicious',
        'suspicious_reason',
        'created_at',
    )
    fieldsets = (
        ('기본 정보', {'fields': ('user', 'event_type', 'created_at')}),
        ('접속 환경', {'fields': ('ip_address', 'device_summary', 'user_agent', 'session_key', 'path')}),
        ('학습 대상', {'fields': ('course_id_value', 'course_title', 'lesson_id_value', 'lesson_title')}),
        ('주의 확인', {'fields': ('is_suspicious', 'suspicious_reason')}),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50

    @admin.display(description='주의 사유')
    def short_reason(self, obj):
        return obj.suspicious_reason or '-'

    def has_add_permission(self, request):
        return False
