from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html

from courses.models import Course
from .models import InstructorEarning, RefundRecord, RevenueRecord, TeachingAssignment
from .services import advance_earnings, post_refund, post_revenue


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'course', 'lesson', 'terms_display', 'starts_on', 'ends_on')
    list_filter = ('method', 'applies_to_renewals', 'course')
    search_fields = ('instructor__username', 'instructor__name', 'course__title', 'lesson__title')
    autocomplete_fields = ('instructor', 'course', 'lesson')
    fieldsets = (
        ('담당 범위', {'fields': ('instructor', 'course', 'lesson')}),
        ('강사료 약정', {'fields': ('method', 'fixed_amount', 'allocation_percent', 'royalty_percent', 'applies_to_renewals'),
            'description': '정액은 건당 지급액, 비율은 실제 입금액 × 배분 비중 × 지급률로 계산합니다. 원 미만은 버립니다. '
                           '환불 시 정액·비율 모두 환불 비율만큼 차감합니다. 세금·공제 전 약정 강사료이며 자동 송금하지 않습니다.'}),
        ('적용 기간', {'fields': ('starts_on', 'ends_on', 'note'),
            'description': '입금 확인일 기준입니다. 기준 변경 시 기존 종료일을 지정하고 다음 날부터 적용할 새 기준을 등록하세요.'}),
    )

    def save_model(self, request, obj, form, change):
        Course.objects.select_for_update().get(pk=obj.course_id)
        super().save_model(request, obj, form, change)

    @admin.display(description='지급 기준')
    def terms_display(self, obj):
        return obj.terms_label


class PostedRecordAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.posted_at)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.posted_at:
            return tuple(f.name for f in self.model._meta.fields)
        return ('posted_at', 'posted_by')

    def has_delete_permission(self, request, obj=None):
        # Retain financial history, including records awaiting verification.
        return False

    def run_posting(self, request, queryset, service):
        count = 0
        for pk in queryset.order_by('pk').values_list('pk', flat=True):
            try:
                with transaction.atomic():
                    count += bool(service(pk, request.user))
            except ValidationError as exc:
                self.message_user(request, f'{pk}번: {" / ".join(exc.messages)}', level=messages.ERROR)
        self.message_user(request, f'{count}건을 반영했습니다. 이미 반영된 내역은 중복 계산하지 않습니다.')


@admin.register(RevenueRecord)
class RevenueRecordAdmin(PostedRecordAdmin):
    list_display = ('id', 'course', 'kind_label', 'source_link', 'amount', 'received_on', 'verification_status')
    list_filter = ('posted_at', 'course', 'received_on')
    search_fields = ('course__title', 'enrollment__user__username', 'renewal__user__username')
    autocomplete_fields = ('enrollment', 'renewal', 'course')
    actions = ('verify_and_calculate',)

    @admin.display(description='금액 확인 상태', boolean=True)
    def verification_status(self, obj):
        return bool(obj.posted_at)

    @admin.display(description='신청 내역')
    def source_link(self, obj):
        model = 'reenrollmentrequest' if obj.renewal_id else 'enrollment'
        return format_html('<a href="{}">{} #{}</a>', reverse(f'admin:enrollments_{model}_change',
            args=[obj.renewal_id or obj.enrollment_id]), obj.kind_label, obj.renewal_id or obj.enrollment_id)

    @admin.action(description='선택한 거래의 실제 입금액 확인·강사료 계산', permissions=['change'])
    def verify_and_calculate(self, request, queryset):
        self.run_posting(request, queryset, post_revenue)


@admin.register(RefundRecord)
class RefundRecordAdmin(PostedRecordAdmin):
    list_display = ('id', 'revenue', 'amount', 'refunded_on', 'reason', 'posted_at')
    search_fields = ('revenue__course__title', 'reason')
    autocomplete_fields = ('revenue',)
    actions = ('apply_refunds',)

    @admin.action(description='선택한 환불 확인·강사료 차감 반영', permissions=['change'])
    def apply_refunds(self, request, queryset):
        self.run_posting(request, queryset, post_refund)


@admin.register(InstructorEarning)
class InstructorEarningAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'course_title', 'lesson_title', 'occurred_on', 'amount', 'status', 'confirmed_at', 'paid_at')
    list_filter = ('status', 'instructor', 'occurred_on')
    search_fields = ('instructor__username', 'instructor__name', 'course_title', 'lesson_title')
    readonly_fields = tuple(f.name for f in InstructorEarning._meta.fields)
    actions = ('confirm_earnings', 'mark_paid')
    date_hierarchy = 'occurred_on'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='선택한 강사료 정산 확정', permissions=['change'])
    def confirm_earnings(self, request, queryset):
        count = advance_earnings(queryset, request.user)
        self.message_user(request, f'{count}건을 정산 확정했습니다.')

    @admin.action(description='선택한 확정 내역 지급 완료 처리 (실제 송금 후 실행)', permissions=['change'])
    def mark_paid(self, request, queryset):
        count = advance_earnings(queryset, request.user, paid=True)
        self.message_user(request, f'{count}건을 지급 완료로 기록했습니다. 이 기능은 실제 송금을 실행하지 않습니다.')
