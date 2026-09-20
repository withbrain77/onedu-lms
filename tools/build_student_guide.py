"""Build the public student guide from reviewed content and example screenshots.

Usage: python tools/build_student_guide.py [--font path/to/Korean.ttf]
Screenshots in docs/student-guide-assets must contain demonstration data only.
"""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]


def format_text(text):
    text = escape(text).replace('\n', '<br/>')
    for url in ['https://onedu.withbrain.kr/help/', 'https://onedu.withbrain.kr']:
        # The longer help URL is handled separately to avoid nested links.
        if url in text:
            text = text.replace(url, f'<link href="{url}" color="#08756f">{url}</link>')
            break
    text = text.replace('withbrain77@daum.net', '<link href="mailto:withbrain77@daum.net" color="#08756f">withbrain77@daum.net</link>')
    return text


def build(font=None):
    candidates = [Path(font)] if font else [Path('C:/Windows/Fonts/malgun.ttf'), Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf')]
    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        raise SystemExit('Supply --font with a Korean TrueType font.')
    pdfmetrics.registerFont(TTFont('GuideKorean', str(font_path)))
    content = json.loads((ROOT / 'docs/student-guide.json').read_text(encoding='utf8'))
    output = ROOT / 'static/docs/onedu-student-user-manual.pdf'
    style = ParagraphStyle('Body', fontName='GuideKorean', fontSize=10.5, leading=17, textColor=colors.HexColor('#243748'), wordWrap='CJK', alignment=TA_LEFT, spaceAfter=7)
    heading = ParagraphStyle('Heading', parent=style, fontSize=13, leading=20, textColor=colors.HexColor('#08756f'), spaceBefore=11, spaceAfter=5)
    title = ParagraphStyle('Title', parent=style, fontSize=24, leading=33, textColor=colors.HexColor('#102433'), spaceAfter=12)
    caption = ParagraphStyle('Caption', parent=style, fontSize=8, leading=12, textColor=colors.HexColor('#596c79'), spaceAfter=8)
    story = []
    for index, page in enumerate(content['pages'], 1):
        if index > 1:
            story.append(PageBreak())
        story.extend([Paragraph(f'{index:02d} / {escape(page["title"])}', title), Paragraph(escape(page['intro']), style), Spacer(1, 8)])
        if page.get('image'):
            screenshot = ROOT / 'docs/student-guide-assets' / page['image']
            image = Image(str(screenshot))
            ratio = min(499 / image.imageWidth, 190 / image.imageHeight)
            image.drawWidth, image.drawHeight = image.imageWidth * ratio, image.imageHeight * ratio
            story.extend([image, Spacer(1, 5), Paragraph(escape(page['caption']), caption)])
        for section in page['sections']:
            block = [Paragraph(escape(section['title']), heading)]
            if 'text' in section:
                block.append(Paragraph(format_text(section['text']), style))
            for item in section.get('items', []):
                block.append(Paragraph('• ' + escape(item), style))
            story.append(KeepTogether(block))

    def decorate(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setTitle(content['title'])
        canvas.setAuthor('위드브레인연구소')
        canvas.setFont('GuideKorean', 8)
        canvas.setFillColor(colors.HexColor('#08756f'))
        canvas.drawString(48, height - 33, '위드브레인연구소 아카데미 · 이용 가이드')
        canvas.setStrokeColor(colors.HexColor('#d8e9e7'))
        canvas.line(48, 40, width - 48, 40)
        canvas.setFillColor(colors.HexColor('#596c79'))
        canvas.drawString(48, 25, f'개정 {content["revision"]}  |  onedu.withbrain.kr')
        canvas.drawRightString(width - 48, 25, str(doc.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=57, bottomMargin=54)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font')
    build(parser.parse_args().font)
