from django.contrib import admin

from .models import Enrollment, ReEnrollmentRequest


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
        'created_at',
    )
    list_filter = ('status', 'is_completed', 'course', 'start_date', 'end_date', 'created_at')
    search_fields = ('user__username', 'user__name', 'user__email', 'course__title')
    list_editable = ('status', 'start_date', 'end_date')
    autocomplete_fields = ('user', 'course', 'approved_by')
    readonly_fields = ('approved_at', 'created_at', 'updated_at', 'completed_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('user', 'course', 'approved_by')
    list_per_page = 50
    fieldsets = (
        ('신청 정보', {'fields': ('user', 'course', 'status')}),
        ('수강 기간', {'fields': ('start_date', 'end_date')}),
        ('승인/반려', {'fields': ('approved_by', 'approved_at', 'rejected_reason')}),
        ('수료', {'fields': ('is_completed', 'completed_at', 'completion_progress_percent', 'completion_note')}),
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
        if obj.status == Enrollment.Status.APPROVED and not obj.approved_by_id:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


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
