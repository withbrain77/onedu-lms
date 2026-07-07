from django.contrib import admin

from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'student_username',
        'student_name',
        'course_title',
        'status',
        'start_date',
        'end_date',
        'days_remaining',
        'created_at',
    )
    list_filter = ('status', 'course', 'start_date', 'end_date', 'created_at')
    search_fields = ('user__username', 'user__name', 'user__email', 'course__title')
    list_editable = ('status', 'start_date', 'end_date')
    autocomplete_fields = ('user', 'course', 'approved_by')
    readonly_fields = ('approved_at', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('user', 'course', 'approved_by')
    list_per_page = 50
    fieldsets = (
        ('신청 정보', {'fields': ('user', 'course', 'status')}),
        ('수강 기간', {'fields': ('start_date', 'end_date')}),
        ('승인/반려', {'fields': ('approved_by', 'approved_at', 'rejected_reason')}),
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

    def save_model(self, request, obj, form, change):
        if obj.status == Enrollment.Status.APPROVED and not obj.approved_by_id:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)
