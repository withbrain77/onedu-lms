from django import forms
from django.contrib import admin
from django.utils.html import format_html

from accounts.models import AccountWithdrawalRequest

from .models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from .notifications import notify_enrollment_approved


BLOCKING_WITHDRAWAL_STATUSES = (
    AccountWithdrawalRequest.Status.REQUESTED,
    AccountWithdrawalRequest.Status.PROCESSING,
    AccountWithdrawalRequest.Status.COMPLETED,
)


def _approval_block_reason_for_user(user, object_label='수강 신청'):
    if not user:
        return ''
    if not user.is_active:
        return f'비활성화된 계정은 {object_label}을 승인할 수 없습니다. 반려 또는 취소로 정리해 주세요.'

    withdrawal_request = (
        AccountWithdrawalRequest.objects
        .filter(user=user, status__in=BLOCKING_WITHDRAWAL_STATUSES)
        .order_by('-requested_at')
        .first()
    )
    if withdrawal_request:
        return (
            f'탈퇴 요청이 접수되었거나 처리된 회원은 {object_label}을 승인할 수 없습니다. '
            '계정 탈퇴 요청 상태를 먼저 확인해 주세요.'
        )
    return ''


def _student_account_status_badge(user):
    if not user:
        return '-'
    if not user.is_active:
        return format_html('<span class="onedu-admin-badge is-danger">비활성</span>')

    withdrawal_request = (
        AccountWithdrawalRequest.objects
        .filter(user=user, status__in=BLOCKING_WITHDRAWAL_STATUSES)
        .order_by('-requested_at')
        .first()
    )
    if not withdrawal_request:
        return format_html('<span class="onedu-admin-badge is-success">정상</span>')
    if withdrawal_request.status == AccountWithdrawalRequest.Status.COMPLETED:
        return format_html('<span class="onedu-admin-badge is-danger">탈퇴 완료</span>')
    return format_html('<span class="onedu-admin-badge is-warning">탈퇴 요청</span>')


class EnrollmentAdminForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        user = cleaned_data.get('user') or getattr(self.instance, 'user', None)
        previous_status = None
        if self.instance and self.instance.pk:
            previous_status = (
                Enrollment.objects
                .filter(pk=self.instance.pk)
                .values_list('status', flat=True)
                .first()
            )

        is_new_approval = (
            status == Enrollment.Status.APPROVED
            and previous_status != Enrollment.Status.APPROVED
        )
        if is_new_approval:
            reason = _approval_block_reason_for_user(user, object_label='수강 신청')
            if reason:
                raise forms.ValidationError(reason)
        return cleaned_data


class ReEnrollmentRequestAdminForm(forms.ModelForm):
    class Meta:
        model = ReEnrollmentRequest
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        user = cleaned_data.get('user') or getattr(self.instance, 'user', None)
        previous_status = None
        if self.instance and self.instance.pk:
            previous_status = (
                ReEnrollmentRequest.objects
                .filter(pk=self.instance.pk)
                .values_list('status', flat=True)
                .first()
            )

        is_new_approval = (
            status == ReEnrollmentRequest.Status.APPROVED
            and previous_status != ReEnrollmentRequest.Status.APPROVED
        )
        if is_new_approval:
            reason = _approval_block_reason_for_user(user, object_label='재수강 신청')
            if reason:
                raise forms.ValidationError(reason)
        return cleaned_data


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    form = EnrollmentAdminForm
    list_display = (
        'student_username',
        'student_name',
        'student_account_status',
        'course_title',
        'status',
        'start_date',
        'end_date',
        'remaining_days',
        'is_completed',
        'completed_at',
        'expiry_notice_7d_sent_at',
        'created_at',
    )
    list_filter = ('status', 'is_completed', 'user__is_active', 'course', 'start_date', 'end_date', 'created_at')
    search_fields = ('user__username', 'user__name', 'user__email', 'course__title')
    list_editable = ('status', 'start_date', 'end_date')
    autocomplete_fields = ('user', 'course', 'approved_by')
    readonly_fields = ('approved_at', 'created_at', 'updated_at', 'completed_at', 'expiry_notice_7d_sent_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('user', 'course', 'approved_by')
    list_per_page = 50
    fieldsets = (
        ('신청 정보', {'fields': ('user', 'course', 'status')}),
        ('수강 기간', {'fields': ('start_date', 'end_date')}),
        ('승인/반려', {'fields': ('approved_by', 'approved_at', 'rejected_reason')}),
        ('수료', {'fields': ('is_completed', 'completed_at', 'completion_progress_percent', 'completion_note')}),
        ('알림', {'fields': ('expiry_notice_7d_sent_at',)}),
        ('기록', {'fields': ('created_at', 'updated_at')}),
    )

    class Media:
        js = ('js/admin_enrollment_period_shortcuts.js',)

    @admin.display(description='아이디', ordering='user__username')
    def student_username(self, obj):
        return obj.user.username

    @admin.display(description='수강생', ordering='user__name')
    def student_name(self, obj):
        return obj.user.display_name

    @admin.display(description='계정 상태', ordering='user__is_active')
    def student_account_status(self, obj):
        return _student_account_status_badge(obj.user)

    @admin.display(description='강의', ordering='course__title')
    def course_title(self, obj):
        return obj.course.title

    @admin.display(description='남은 기간')
    def remaining_days(self, obj):
        days = obj.days_remaining
        if days is None:
            return '-'
        return days

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                Enrollment.objects
                .filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )
        should_notify_approval = (
            obj.status == Enrollment.Status.APPROVED
            and previous_status != Enrollment.Status.APPROVED
        )
        if obj.status == Enrollment.Status.APPROVED and not obj.approved_by_id:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)
        if should_notify_approval:
            notify_enrollment_approved(obj)


@admin.register(ReEnrollmentRequest)
class ReEnrollmentRequestAdmin(admin.ModelAdmin):
    form = ReEnrollmentRequestAdminForm
    list_display = (
        'student_username',
        'student_name',
        'student_account_status',
        'course_title',
        'status',
        'requested_at',
        'processed_at',
        'processed_by',
        'extension_start_date',
        'extension_end_date',
    )
    list_filter = (
        'status',
        'user__is_active',
        'course',
        'requested_at',
        'processed_at',
        'extension_start_date',
        'extension_end_date',
    )
    search_fields = (
        'user__username',
        'user__name',
        'user__email',
        'course__title',
        'reason',
        'admin_note',
    )
    list_editable = ('status', 'extension_start_date', 'extension_end_date')
    autocomplete_fields = ('user', 'course', 'enrollment', 'processed_by')
    readonly_fields = ('requested_at', 'processed_at')
    date_hierarchy = 'requested_at'
    ordering = ('-requested_at',)
    list_select_related = ('user', 'course', 'enrollment', 'processed_by')
    list_per_page = 50
    fieldsets = (
        ('신청 정보', {'fields': ('user', 'course', 'enrollment', 'reason', 'status')}),
        ('연장 기간', {'fields': ('extension_start_date', 'extension_end_date')}),
        ('처리 정보', {'fields': ('processed_by', 'processed_at', 'admin_note')}),
        ('기록', {'fields': ('requested_at',)}),
    )

    @admin.display(description='아이디', ordering='user__username')
    def student_username(self, obj):
        return obj.user.username

    @admin.display(description='수강생', ordering='user__name')
    def student_name(self, obj):
        return obj.user.display_name

    @admin.display(description='계정 상태', ordering='user__is_active')
    def student_account_status(self, obj):
        return _student_account_status_badge(obj.user)

    @admin.display(description='강의', ordering='course__title')
    def course_title(self, obj):
        return obj.course.title

    def save_model(self, request, obj, form, change):
        if obj.status in (ReEnrollmentRequest.Status.APPROVED, ReEnrollmentRequest.Status.REJECTED):
            if not obj.processed_by_id:
                obj.processed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'kind',
        'status',
        'recipient_email',
        'user_label',
        'course_title',
        'subject',
        'sent_at',
    )
    list_filter = ('kind', 'status', 'created_at', 'sent_at')
    search_fields = (
        'recipient_email',
        'subject',
        'user_label',
        'course_title',
        'error_message',
        'enrollment__user__username',
        'enrollment__user__name',
        'enrollment__course__title',
    )
    readonly_fields = (
        'enrollment',
        'kind',
        'status',
        'recipient_email',
        'subject',
        'user_id_value',
        'user_label',
        'course_id_value',
        'course_title',
        'error_detail',
        'sent_at',
        'created_at',
    )
    fieldsets = (
        ('메일 정보', {'fields': ('kind', 'status', 'recipient_email', 'subject')}),
        ('관련 수강', {'fields': ('enrollment', 'user_id_value', 'user_label', 'course_id_value', 'course_title')}),
        ('결과', {'fields': ('sent_at', 'error_detail')}),
        ('기록', {'fields': ('created_at',)}),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('enrollment', 'enrollment__user', 'enrollment__course')
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    @admin.display(description='오류 상세 / 서버 로그 요약')
    def error_detail(self, obj):
        if obj.error_message:
            message = obj.error_message
        elif obj.status == EmailDeliveryLog.Status.FAILED:
            message = '실패로 기록되었지만 저장된 오류 상세가 없습니다. 이전 버전에서 생성된 로그일 수 있습니다.'
        else:
            message = '기록된 오류 내용이 없습니다.'
        return format_html('<pre class="onedu-admin-error-detail">{}</pre>', message)
