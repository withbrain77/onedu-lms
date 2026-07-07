from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        'certificate_no',
        'user',
        'course',
        'issued_at',
        'is_active',
        'revoked_at',
    )
    list_filter = ('is_active', 'course', 'issued_at', 'revoked_at')
    search_fields = (
        'certificate_no',
        'verification_code',
        'user__username',
        'user__name',
        'user__email',
        'course__title',
    )
    readonly_fields = (
        'certificate_no',
        'verification_code',
        'issued_at',
    )
    list_select_related = ('user', 'course', 'enrollment')
    date_hierarchy = 'issued_at'
