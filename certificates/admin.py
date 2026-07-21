from types import SimpleNamespace

from django.contrib import admin
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Certificate, CertificateDesign
from .services import render_certificate_pdf


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
    list_display = ('name', 'issuer_name', 'is_active', 'preview_pdf_link', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('name', 'issuer_name', 'issuer_subtitle', 'representative_name')
    fieldsets = (
        ('기본 설정', {'fields': ('name', 'is_active', 'certificate_title', 'preview_pdf_link')}),
        ('발급 기관', {'fields': ('issuer_name', 'issuer_subtitle', 'representative_name')}),
        ('문구와 색상', {'fields': ('completion_statement', 'footer_note', 'accent_color')}),
        ('이미지', {'fields': ('logo_image', 'seal_image')}),
    )
    readonly_fields = ('preview_pdf_link', 'updated_at')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/preview/',
                self.admin_site.admin_view(self.preview_pdf),
                name='certificates_certificatedesign_preview',
            ),
        ]
        return custom_urls + urls

    @admin.display(description='미리보기')
    def preview_pdf_link(self, obj):
        if not obj or not obj.pk:
            return '저장 후 미리보기 가능'
        url = reverse('admin:certificates_certificatedesign_preview', args=[obj.pk])
        return format_html(
            '<a class="onedu-admin-inline-button" href="{}" target="_blank" rel="noopener">미리보기 PDF</a>',
            url,
        )

    def preview_pdf(self, request, object_id):
        design = get_object_or_404(CertificateDesign, pk=object_id)
        now = timezone.now()
        sample_certificate = SimpleNamespace(
            user=SimpleNamespace(display_name='홍길동'),
            course=SimpleNamespace(title='샘플 교육 과정'),
            enrollment=SimpleNamespace(completed_at=now),
            issued_at=now,
            certificate_no=f'PREVIEW-{now:%Y%m%d}',
            verification_code='preview-verification-code-000000000000',
        )
        verify_url = request.build_absolute_uri(reverse('certificates:verify'))
        pdf_buffer = render_certificate_pdf(sample_certificate, verify_url=verify_url, design=design)
        filename = f'certificate-design-{design.pk}-preview.pdf'
        return FileResponse(pdf_buffer, as_attachment=False, filename=filename, content_type='application/pdf')
