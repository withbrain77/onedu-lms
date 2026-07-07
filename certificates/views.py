from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Certificate
from .services import render_certificate_pdf


@login_required
def download_certificate(request, pk):
    certificate = get_object_or_404(
        Certificate.objects.select_related('user', 'course', 'enrollment'),
        pk=pk,
        is_active=True,
        revoked_at__isnull=True,
    )
    if certificate.user_id != request.user.pk and not request.user.is_staff:
        raise Http404('Certificate not found')
    if not certificate.enrollment.is_completed:
        raise Http404('Certificate not found')

    pdf_buffer = render_certificate_pdf(certificate)
    filename = f'{certificate.certificate_no}.pdf'
    return FileResponse(pdf_buffer, as_attachment=True, filename=filename, content_type='application/pdf')
