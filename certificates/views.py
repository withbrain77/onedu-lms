from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Certificate
from .services import render_certificate_pdf


@require_http_methods(['GET', 'POST'])
def verify_certificate(request):
    code = ''
    certificate = None
    is_submitted = False
    is_invalid_or_revoked = False

    if request.method == 'POST':
        code = request.POST.get('verification_code', '').strip()
        is_submitted = True
    else:
        code = request.GET.get('code', '').strip()
        is_submitted = bool(code)

    if code:
        certificate = (
            Certificate.objects
            .select_related('user', 'course', 'enrollment')
            .filter(verification_code__iexact=code)
            .first()
        )
        if not certificate or certificate.is_revoked or not certificate.enrollment.is_completed:
            certificate = None
            is_invalid_or_revoked = True
    elif is_submitted:
        is_invalid_or_revoked = True

    completed_date = None
    if certificate:
        completed_at = certificate.enrollment.completed_at or certificate.issued_at
        completed_date = timezone.localtime(completed_at).date()

    return render(
        request,
        'certificates/verify.html',
        {
            'code': code,
            'certificate': certificate,
            'completed_date': completed_date,
            'issuer_name': settings.CERTIFICATE_ISSUER_NAME,
            'is_submitted': is_submitted,
            'is_invalid_or_revoked': is_invalid_or_revoked,
        },
    )


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

    verify_url = request.build_absolute_uri(reverse('certificates:verify'))
    pdf_buffer = render_certificate_pdf(certificate, verify_url=verify_url)
    filename = f'{certificate.certificate_no}.pdf'
    return FileResponse(pdf_buffer, as_attachment=True, filename=filename, content_type='application/pdf')
