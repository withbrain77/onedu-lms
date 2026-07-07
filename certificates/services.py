from io import BytesIO
import hashlib
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfdoc
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import Certificate


KOREAN_FONT_NAME = 'OneduKorean'


def _md5_compat(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return hashlib.md5(*args, **kwargs)


pdfdoc.md5 = _md5_compat


def _register_certificate_font():
    candidates = []
    if settings.CERTIFICATE_FONT_PATH:
        candidates.append(settings.CERTIFICATE_FONT_PATH)
    candidates.extend([
        r'C:\Windows\Fonts\malgun.ttf',
        r'C:\Windows\Fonts\malgunbd.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ])
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            pdfmetrics.registerFont(TTFont(KOREAN_FONT_NAME, str(path)))
            return KOREAN_FONT_NAME
    return 'Helvetica'


def get_or_create_certificate(enrollment):
    certificate, _created = Certificate.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            'user': enrollment.user,
            'course': enrollment.course,
        },
    )
    return certificate


def render_certificate_pdf(certificate):
    font_name = _register_certificate_font()
    buffer = BytesIO()
    page_size = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    pdf.setStrokeColor(colors.HexColor('#2563eb'))
    pdf.setLineWidth(4)
    pdf.rect(36, 36, width - 72, height - 72)

    pdf.setFillColor(colors.HexColor('#0f172a'))
    pdf.setFont(font_name, 28)
    pdf.drawCentredString(width / 2, height - 110, '수 료 증')

    pdf.setFont(font_name, 14)
    pdf.setFillColor(colors.HexColor('#475569'))
    pdf.drawCentredString(width / 2, height - 150, f'Certificate No. {certificate.certificate_no}')

    pdf.setFillColor(colors.HexColor('#111827'))
    pdf.setFont(font_name, 18)
    pdf.drawCentredString(width / 2, height - 210, f'성명: {certificate.user.display_name}')
    pdf.drawCentredString(width / 2, height - 250, f'강의명: {certificate.course.title}')

    completed_at = certificate.enrollment.completed_at or certificate.issued_at
    completed_date = timezone.localtime(completed_at).strftime('%Y년 %m월 %d일')
    issued_date = timezone.localtime(certificate.issued_at).strftime('%Y년 %m월 %d일')

    pdf.setFont(font_name, 14)
    pdf.drawCentredString(width / 2, height - 305, f'위 사람은 {completed_date} 위 교육 과정을 수료하였음을 증명합니다.')
    pdf.drawCentredString(width / 2, height - 350, f'발급일: {issued_date}')

    pdf.setFillColor(colors.HexColor('#334155'))
    pdf.drawCentredString(width / 2, height - 405, settings.CERTIFICATE_ISSUER_NAME)

    pdf.setFont(font_name, 10)
    pdf.setFillColor(colors.HexColor('#64748b'))
    pdf.drawCentredString(width / 2, 72, f'검증 코드: {certificate.verification_code}')

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer
