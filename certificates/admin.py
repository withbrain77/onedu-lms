from django.contrib import admin

from .models import Certificate, CertificateDesign


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


@admin.register(CertificateDesign)
class CertificateDesignAdmin(admin.ModelAdmin):
    list_display = ('name', 'issuer_name', 'is_active', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('name', 'issuer_name', 'issuer_subtitle', 'representative_name')
    fieldsets = (
        ('기본 설정', {'fields': ('name', 'is_active', 'certificate_title')}),
        ('발급 기관', {'fields': ('issuer_name', 'issuer_subtitle', 'representative_name')}),
        ('문구와 색상', {'fields': ('completion_statement', 'footer_note', 'accent_color')}),
        ('이미지', {'fields': ('logo_image', 'seal_image')}),
    )
    readonly_fields = ('updated_at',)
