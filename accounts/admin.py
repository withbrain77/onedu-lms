from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import AccessLog, AccountWithdrawalRequest, User
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
        return format_html('<a class="onedu-admin-inline-button" href="{}">보기</a>', url)

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


@admin.register(AccountWithdrawalRequest)
class AccountWithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        'requested_at',
        'user_label',
        'email_snapshot',
        'short_reason',
        'status',
        'processed_at',
        'processed_by',
    )
    list_filter = ('status', 'requested_at', 'processed_at')
    search_fields = (
        'username_snapshot',
        'name_snapshot',
        'email_snapshot',
        'phone_snapshot',
        'reason',
        'admin_note',
        'user__username',
        'user__email',
        'user__name',
    )
    readonly_fields = (
        'user',
        'username_snapshot',
        'name_snapshot',
        'email_snapshot',
        'phone_snapshot',
        'reason',
        'requested_at',
        'processed_at',
        'processed_by',
    )
    fieldsets = (
        ('요청 정보', {
            'fields': (
                'user',
                'username_snapshot',
                'name_snapshot',
                'email_snapshot',
                'phone_snapshot',
                'reason',
                'requested_at',
            )
        }),
        ('처리', {
            'fields': (
                'status',
                'processed_at',
                'processed_by',
                'admin_note',
            )
        }),
    )
    actions = ('mark_processing', 'complete_and_deactivate_users', 'cancel_requests')
    date_hierarchy = 'requested_at'
    ordering = ('-requested_at',)
    list_per_page = 50

    @admin.display(description='사용자')
    def user_label(self, obj):
        return obj.name_snapshot or obj.username_snapshot or '-'

    @admin.display(description='요청 사유')
    def short_reason(self, obj):
        if not obj.reason:
            return '-'
        if len(obj.reason) <= 40:
            return obj.reason
        return f'{obj.reason[:40]}...'

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = AccountWithdrawalRequest.objects.filter(pk=obj.pk).values_list('status', flat=True).first()

        if obj.status in (obj.Status.COMPLETED, obj.Status.CANCELED) and previous_status != obj.status:
            obj.processed_at = timezone.now()
            obj.processed_by = request.user
        elif obj.status == obj.Status.PROCESSING and previous_status != obj.status:
            obj.processed_by = request.user

        super().save_model(request, obj, form, change)

        if obj.status == obj.Status.COMPLETED:
            self._deactivate_user(obj)

    def _deactivate_user(self, obj):
        user = obj.user
        if user and user.is_active and not user.is_staff and not user.is_superuser:
            user.is_active = False
            user.save(update_fields=['is_active'])

    @admin.action(description='처리 중으로 변경')
    def mark_processing(self, request, queryset):
        updated = queryset.filter(status=AccountWithdrawalRequest.Status.REQUESTED).update(
            status=AccountWithdrawalRequest.Status.PROCESSING,
            processed_by_id=request.user.pk,
        )
        self.message_user(request, f'{updated}건을 처리 중으로 변경했습니다.')

    @admin.action(description='처리 완료 및 일반 계정 비활성화')
    def complete_and_deactivate_users(self, request, queryset):
        completed = 0
        now = timezone.now()
        for withdrawal_request in queryset.exclude(status=AccountWithdrawalRequest.Status.COMPLETED):
            withdrawal_request.status = AccountWithdrawalRequest.Status.COMPLETED
            withdrawal_request.processed_at = now
            withdrawal_request.processed_by = request.user
            withdrawal_request.save(update_fields=['status', 'processed_at', 'processed_by'])
            self._deactivate_user(withdrawal_request)
            completed += 1
        self.message_user(request, f'{completed}건을 처리 완료했습니다.')

    @admin.action(description='요청 취소로 변경')
    def cancel_requests(self, request, queryset):
        updated = queryset.exclude(status=AccountWithdrawalRequest.Status.CANCELED).update(
            status=AccountWithdrawalRequest.Status.CANCELED,
            processed_at=timezone.now(),
            processed_by_id=request.user.pk,
        )
        self.message_user(request, f'{updated}건을 요청 취소로 변경했습니다.')
