from django.contrib import admin

from .models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from .notifications import notify_enrollment_approved


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'student_username',
        'student_name',
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
    list_filter = ('status', 'is_completed', 'course', 'start_date', 'end_date', 'created_at')
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

    @admin.display(description='아이디', ordering='user__username')
    def student_username(self, obj):
        return obj.user.username

    @admin.display(description='수강생', ordering='user__name')
    def student_name(self, obj):
        return obj.user.display_name

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
    list_display = (
        'student_username',
        'student_name',
        'course_title',
        'status',
        'requested_at',
        'processed_at',
        'processed_by',
        'extension_start_date',
        'extension_end_date',
    )
    list_filter = ('status', 'course', 'requested_at', 'processed_at', 'extension_start_date', 'extension_end_date')
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
        'error_message',
        'sent_at',
        'created_at',
    )
    fieldsets = (
        ('메일 정보', {'fields': ('kind', 'status', 'recipient_email', 'subject')}),
        ('관련 수강', {'fields': ('enrollment', 'user_id_value', 'user_label', 'course_id_value', 'course_title')}),
        ('결과', {'fields': ('sent_at', 'error_message')}),
        ('기록', {'fields': ('created_at',)}),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('enrollment', 'enrollment__user', 'enrollment__course')
    list_per_page = 50

    def has_add_permission(self, request):
        return False
