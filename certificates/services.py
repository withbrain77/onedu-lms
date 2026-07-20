from io import BytesIO
import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfdoc
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import Certificate, CertificateDesign


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


def get_active_certificate_design():
    return CertificateDesign.objects.filter(is_active=True).order_by('-updated_at').first()


def _hex_color(value, fallback='#007B74'):
    if not value:
        value = fallback
    value = value.strip()
    if not value.startswith('#'):
        value = f'#{value}'
    try:
        return colors.HexColor(value)
    except ValueError:
        return colors.HexColor(fallback)


def _field_path(file_field):
    if not file_field:
        return ''
    try:
        if file_field.name and file_field.storage.exists(file_field.name):
            return file_field.path
    except (NotImplementedError, ValueError, OSError):
        return ''
    return ''


def _default_logo_path():
    static_path = finders.find('img/withbrain-logo.png')
    return static_path or ''


def _draw_image(pdf, path, x, y, width, height):
    if not path:
        return False
    try:
        pdf.drawImage(
            ImageReader(path),
            x,
            y,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask='auto',
            anchor='c',
        )
        return True
    except Exception:
        return False


def _fit_text(pdf, text, font_name, initial_size, max_width, min_size=9):
    size = initial_size
    while size > min_size and pdf.stringWidth(text, font_name, size) > max_width:
        size -= 1
    return size


def _draw_centered_wrapped(pdf, text, x, y, max_width, font_name, font_size, leading, fill_color):
    words = str(text).split()
    if not words:
        return y
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if current and pdf.stringWidth(candidate, font_name, font_size) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    pdf.setFont(font_name, font_size)
    pdf.setFillColor(fill_color)
    for line in lines[:3]:
        pdf.drawCentredString(x, y, line)
        y -= leading
    return y


def render_certificate_pdf(certificate, verify_url=''):
    font_name = _register_certificate_font()
    design = get_active_certificate_design()
    buffer = BytesIO()
    page_size = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size
    accent = _hex_color(getattr(design, 'accent_color', ''), '#007B74')
    navy = colors.HexColor('#001B3A')
    muted = colors.HexColor('#64748B')
    body = colors.HexColor('#152237')
    light_line = colors.HexColor('#D7E7E5')
    issuer_name = getattr(design, 'issuer_name', '') or settings.CERTIFICATE_ISSUER_NAME
    issuer_subtitle = getattr(design, 'issuer_subtitle', '') or 'WITHBRAIN INSTITUTE'
    certificate_title = getattr(design, 'certificate_title', '') or '수 료 증'
    completion_statement = (
        getattr(design, 'completion_statement', '')
        or '위 사람은 본 교육 과정을 성실히 이수하였음을 증명합니다.'
    )
    footer_note = (
        getattr(design, 'footer_note', '')
        or '본 수료증은 ONEDU LMS 수료증 검증 페이지에서 진위 여부를 확인할 수 있습니다.'
    )
    representative_name = getattr(design, 'representative_name', '') or ''

    # Background and modern certificate frame
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#F4FAF9'))
    pdf.rect(0, 0, width, 74, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#F8FBFD'))
    pdf.rect(0, height - 82, width, 82, fill=1, stroke=0)

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(3)
    pdf.roundRect(36, 34, width - 72, height - 68, 10, stroke=1, fill=0)
    pdf.setStrokeColor(light_line)
    pdf.setLineWidth(1)
    pdf.roundRect(50, 48, width - 100, height - 96, 8, stroke=1, fill=0)

    logo_path = _field_path(design.logo_image) if design else ''
    if not logo_path:
        logo_path = _default_logo_path()
    if not _draw_image(pdf, logo_path, 70, height - 82, 130, 54):
        pdf.setFillColor(accent)
        pdf.setFont(font_name, 16)
        pdf.drawString(70, height - 66, issuer_name)

    pdf.setFillColor(accent)
    pdf.setFont(font_name, 9)
    pdf.drawRightString(width - 70, height - 58, 'ONEDU LMS CERTIFICATE')
    pdf.setFillColor(muted)
    pdf.drawRightString(width - 70, height - 74, f'Certificate No. {certificate.certificate_no}')

    pdf.setFillColor(navy)
    title_size = _fit_text(pdf, certificate_title, font_name, 34, 300, min_size=24)
    pdf.setFont(font_name, title_size)
    pdf.drawCentredString(width / 2, height - 126, certificate_title)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(2)
    pdf.line(width / 2 - 54, height - 142, width / 2 + 54, height - 142)

    pdf.setFont(font_name, 11)
    pdf.setFillColor(muted)
    pdf.drawCentredString(width / 2, height - 172, 'This certifies that')

    student_name = certificate.user.display_name
    student_size = _fit_text(pdf, student_name, font_name, 30, 360, min_size=20)
    pdf.setFillColor(navy)
    pdf.setFont(font_name, student_size)
    pdf.drawCentredString(width / 2, height - 213, student_name)
    pdf.setStrokeColor(light_line)
    pdf.setLineWidth(1)
    pdf.line(width / 2 - 170, height - 226, width / 2 + 170, height - 226)

    completed_at = certificate.enrollment.completed_at or certificate.issued_at
    completed_date = timezone.localtime(completed_at).strftime('%Y년 %m월 %d일')
    issued_date = timezone.localtime(certificate.issued_at).strftime('%Y년 %m월 %d일')

    pdf.setFillColor(muted)
    pdf.setFont(font_name, 10)
    pdf.drawCentredString(width / 2, height - 256, 'has successfully completed the following program')

    y_after_course = _draw_centered_wrapped(
        pdf,
        certificate.course.title,
        width / 2,
        height - 288,
        560,
        font_name,
        18,
        24,
        body,
    )

    pdf.setFont(font_name, 13)
    pdf.setFillColor(body)
    pdf.drawCentredString(width / 2, y_after_course - 18, completion_statement)

    info_y = 154
    info_items = [
        ('수료일', completed_date),
        ('발급일', issued_date),
        ('검증 코드', certificate.verification_code),
    ]
    start_x = 90
    col_w = (width - 180) / 3
    pdf.setStrokeColor(light_line)
    for index, (label, value) in enumerate(info_items):
        x = start_x + col_w * index
        if index:
            pdf.line(x - 14, info_y - 10, x - 14, info_y + 44)
        pdf.setFillColor(muted)
        pdf.setFont(font_name, 9)
        pdf.drawString(x, info_y + 28, label)
        pdf.setFillColor(navy)
        value_size = _fit_text(pdf, value, font_name, 11, col_w - 18, min_size=7)
        pdf.setFont(font_name, value_size)
        pdf.drawString(x, info_y + 6, value)

    issuer_y = 102
    pdf.setFillColor(navy)
    pdf.setFont(font_name, 16)
    pdf.drawCentredString(width / 2, issuer_y, issuer_name)
    pdf.setFillColor(muted)
    pdf.setFont(font_name, 9)
    if representative_name:
        pdf.drawCentredString(width / 2, issuer_y - 18, f'대표 {representative_name}')
    elif issuer_subtitle:
        pdf.drawCentredString(width / 2, issuer_y - 18, issuer_subtitle)

    seal_path = _field_path(design.seal_image) if design else ''
    if seal_path:
        _draw_image(pdf, seal_path, width / 2 + 110, issuer_y - 34, 70, 70)

    pdf.setFont(font_name, 10)
    pdf.setFillColor(muted)
    pdf.drawCentredString(width / 2, 54, footer_note)
    if verify_url:
        pdf.drawCentredString(width / 2, 38, f'수료증 검증: {verify_url}')
    else:
        pdf.drawCentredString(width / 2, 38, '수료증 검증 페이지에서 검증 코드를 입력해 진위 여부를 확인할 수 있습니다.')

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer
