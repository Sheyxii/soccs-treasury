"""Official receipt as a downloadable A4 PDF, matching the on-screen receipt layout."""
import io
from datetime import timedelta
from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from app.finance.words import peso_words

PLUM, INK, MUTED, RED, LINE = HexColor('#2f1b5c'), HexColor('#1d1829'), HexColor('#4a4358'), HexColor('#a0304f'), HexColor('#b9aed0')
# A Unicode font shows the peso sign; without one the PDF falls back to "PHP".
FONT_CANDIDATES = [
    ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/segoeuib.ttf'),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ('/Library/Fonts/Arial Unicode.ttf', '/Library/Fonts/Arial Unicode.ttf'),
]


def _fonts():
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            if 'Receipt' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Receipt', regular))
                pdfmetrics.registerFont(TTFont('Receipt-Bold', bold))
            return 'Receipt', 'Receipt-Bold', '₱'
    return 'Helvetica', 'Helvetica-Bold', 'PHP '


def build_receipt_pdf(receipt, tx, income, logo_path):
    regular, bold, peso = _fonts()
    money = lambda value: f'{peso}{value:,.2f}'  # noqa: E731
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f'Official receipt {receipt.number}')
    pdf.setAuthor('SOCCS Treasury')
    width, height = A4
    left, right = 20 * mm, width - 20 * mm
    top = height - 20 * mm

    # Header: logo and organization on the left, title, number and date on the right.
    if Path(logo_path).exists():
        pdf.drawImage(ImageReader(str(logo_path)), left, top - 17 * mm, 17 * mm, 17 * mm, mask='auto', preserveAspectRatio=True)
    text_left = left + 21 * mm
    pdf.setFillColor(PLUM)
    pdf.setFont(bold, 11.5)
    org_lines = simpleSplit('Student Organization of the College of Computer Studies', bold, 11.5, 85 * mm)
    y = top - 5 * mm
    for line in org_lines:
        pdf.drawString(text_left, y, line)
        y -= 5 * mm
    pdf.setFillColor(MUTED)
    pdf.setFont(regular, 9.5)
    pdf.drawString(text_left, y, 'Laguna State Polytechnic University, Santa Cruz Campus')

    pdf.setFillColor(PLUM)
    pdf.setFont(bold, 18)
    pdf.drawRightString(right, top - 6 * mm, 'Official receipt')
    pdf.setFont(regular, 10)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(right - 30 * mm, top - 12.5 * mm, 'No.')
    pdf.drawRightString(right - 30 * mm, top - 18 * mm, 'Date')
    pdf.setFont(bold, 11.5)
    pdf.setFillColor(RED)
    pdf.drawRightString(right, top - 12.5 * mm, receipt.number)
    pdf.setFont(bold, 10)
    pdf.setFillColor(INK)
    pdf.drawRightString(right, top - 18 * mm, tx.occurred_on.strftime('%d %B %Y'))

    rule = top - 24 * mm
    pdf.setStrokeColor(PLUM)
    pdf.setLineWidth(2)
    pdf.line(left, rule, right, rule)

    # Body lines, written on dashed lines like a filled-in form.
    rows = [
        ('Received from', tx.member_name or '', f'Student no. {tx.student_number}, BS{tx.program}'),
        ('The amount of', peso_words(tx.amount), None),
        ('For', tx.description, f'Academic year {tx.academic_year.name if tx.academic_year else "not set"}'),
        ('Paid by', tx.method, f'Reference {tx.reference}' if tx.reference else None),
    ]
    y = rule - 13 * mm
    value_left = left + 38 * mm
    for label, value, detail in rows:
        pdf.setFont(regular, 10)
        pdf.setFillColor(MUTED)
        pdf.drawString(left, y, label)
        pdf.setFont(bold, 12)
        pdf.setFillColor(INK)
        lines = simpleSplit(value, bold, 12, right - value_left)
        line_y = y
        for line in lines:
            pdf.drawString(value_left, line_y, line)
            line_y -= 5.5 * mm
        if detail:
            pdf.setFont(regular, 9.5)
            pdf.setFillColor(MUTED)
            pdf.drawString(value_left, line_y + 0.8 * mm, detail)
            line_y -= 4.5 * mm
        underline = line_y + 3 * mm
        pdf.setStrokeColor(LINE)
        pdf.setLineWidth(0.6)
        pdf.setDash(2, 2)
        pdf.line(value_left, underline, right, underline)
        pdf.setDash()
        y = underline - 9 * mm

    # Revenue split (left) and total (right).
    block_top = y - 2 * mm
    if income:
        pdf.setFont(bold, 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(left, block_top, 'Share')
        pdf.drawRightString(left + 62 * mm, block_top, 'Amount')
        pdf.setStrokeColor(HexColor('#ddd5e8'))
        pdf.setLineWidth(0.6)
        pdf.line(left, block_top - 2 * mm, left + 64 * mm, block_top - 2 * mm)
        row_y = block_top - 7 * mm
        for name, value in (('SOCCS', income.soccs_share), ('ITUH', income.ituh_share), ('CSS', income.css_share)):
            pdf.setFont(regular, 10)
            pdf.setFillColor(INK)
            pdf.drawString(left, row_y, name)
            pdf.drawRightString(left + 62 * mm, row_y, money(value))
            pdf.setStrokeColor(HexColor('#eee9f5'))
            pdf.line(left, row_y - 2 * mm, left + 64 * mm, row_y - 2 * mm)
            row_y -= 7 * mm
    pdf.setFont(bold, 10)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(right, block_top, 'Total received')
    pdf.setFont(bold, 24)
    pdf.setFillColor(PLUM)
    pdf.drawRightString(right, block_top - 11 * mm, money(tx.amount))

    # Footer: signature on the right, issue details on the left.
    foot = block_top - 50 * mm
    sign_left, sign_right = right - 70 * mm, right
    pdf.setFont(bold, 11)
    pdf.setFillColor(INK)
    if tx.approver:
        pdf.drawCentredString((sign_left + sign_right) / 2, foot + 2 * mm, tx.approver.full_name)
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.8)
    pdf.line(sign_left, foot, sign_right, foot)
    pdf.setFont(regular, 9.5)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString((sign_left + sign_right) / 2, foot - 5 * mm, 'Received by' + (f', {tx.approver.role.name}' if tx.approver else ''))

    issued = (receipt.issued_at + timedelta(hours=8)).strftime('%d %b %Y, %I:%M %p')
    notes = [f'Issued {issued} for transaction {tx.number}.' + (f' Verified by {tx.verifier.full_name}.' if tx.verified_at else ''),
             'Student details are shown as recorded when the payment was made.']
    pdf.setFont(regular, 8.5)
    note_y = foot + 2 * mm
    for note in notes:
        for line in simpleSplit(note, regular, 8.5, 85 * mm):
            pdf.drawString(left, note_y, line)
            note_y -= 4 * mm

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
