from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


WATERMARK_FONT_NAME = 'OneduWatermarkKorean'


class PDFWatermarkError(Exception):
    pass


def _register_watermark_font():
    if WATERMARK_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return WATERMARK_FONT_NAME

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
            pdfmetrics.registerFont(TTFont(WATERMARK_FONT_NAME, str(path)))
            return WATERMARK_FONT_NAME
    return 'Helvetica'


def _display_name(user):
    name = getattr(user, 'display_name', '') or user.get_full_name() or user.get_username()
    return str(name).strip() or user.get_username()


def _set_alpha(pdf, alpha):
    if hasattr(pdf, 'setFillAlpha'):
        pdf.setFillAlpha(alpha)


def _watermark_overlay(width, height, footer_text, corner_text):
    buffer = BytesIO()
    font_name = _register_watermark_font()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))

    pdf.setFillColor(colors.HexColor('#0f766e'))
    _set_alpha(pdf, 0.5)
    pdf.setFont(font_name, 8.5)
    pdf.drawCentredString(width / 2, 20, footer_text)

    _set_alpha(pdf, 0.12)
    pdf.setFont(font_name, 7)
    pdf.drawRightString(width - 28, height - 22, corner_text)

    _set_alpha(pdf, 1)
    pdf.save()
    buffer.seek(0)
    return buffer


def render_watermarked_pdf(source_path, user, downloaded_at=None):
    downloaded_at = downloaded_at or timezone.localtime()
    local_downloaded_at = timezone.localtime(downloaded_at)
    user_label = _display_name(user)
    footer_text = (
        f'WITHBRAIN 교육자료 · {user_label} · ONEDU LMS · '
        f'다운로드일 {local_downloaded_at:%Y-%m-%d}'
    )
    corner_text = f'{user_label} · ONEDU'

    try:
        reader = PdfReader(str(source_path))
        if reader.is_encrypted:
            decrypt_result = reader.decrypt('')
            if decrypt_result == 0:
                raise PDFWatermarkError('Encrypted PDF cannot be watermarked.')

        writer = PdfWriter()
        for page in reader.pages:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            overlay = PdfReader(_watermark_overlay(width, height, footer_text, corner_text)).pages[0]
            page.merge_page(overlay)
            writer.add_page(page)

        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return output
    except PDFWatermarkError:
        raise
    except Exception as exc:
        raise PDFWatermarkError('PDF watermark rendering failed.') from exc
