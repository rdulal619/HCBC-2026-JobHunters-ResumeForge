"""
resume_pdf.py
Two-step approach:
  1. parse_resume(text) → structured dict
  2. render_*(data, template) → PDF bytes

The AI only touches content (bullet text, summary).
The template controls ALL formatting — fonts, spacing, alignment, dates.
"""

import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, KeepTogether
)

PW = letter[0]   # page width  = 612
PH = letter[1]   # page height = 792
LM = RM = 0.70 * inch
TM = BM = 0.60 * inch
CW = PW - LM - RM   # content width ≈ 7.1 in

# ── Regex helpers ──────────────────────────────────────────────────────────
SECTION_RE = re.compile(
    r'^(SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|PROFILE|ABOUT|'
    r'EXPERIENCE|WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|EMPLOYMENT|'
    r'EDUCATION|ACADEMIC|'
    r'SKILLS?|TECHNICAL SKILLS?|TECH SKILLS?|CORE COMPETENCIES|TECHNOLOGIES|'
    r'PROJECTS?|PORTFOLIO|'
    r'CERTIFICATIONS?|LICENSES?|CREDENTIALS?|'
    r'LANGUAGES?|AWARDS?|ACHIEVEMENTS?|HONORS?|PUBLICATIONS?|'
    r'VOLUNTEER|INVOLVEMENT|ACTIVITIES|LEADERSHIP|INTERESTS?)\s*:?\s*$',
    re.IGNORECASE
)

DATE_RE = re.compile(
    r'(?:'
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}'
    r'|(?:january|february|march|april|june|july|august|september|october|november|december)\s+\d{4}'
    r'|\d{1,2}/\d{4}'
    r'|\d{4}'
    r')'
    r'(?:\s*[-–—]\s*'
    r'(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}'
    r'|(?:january|february|march|april|june|july|august|september|october|november|december)\s+\d{4}'
    r'|\d{1,2}/\d{4}|\d{4}|present|current|now))?',
    re.IGNORECASE
)

BULLET_RE = re.compile(r'^[•\-\*–▸▹◦·]\s*(.+)')


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: Parse plain text → structured dict
# ══════════════════════════════════════════════════════════════════════════
def parse_resume(text: str) -> dict:
    """
    Returns:
    {
      name: str,
      contact: [str, ...],        # phone, email, linkedin, location
      sections: [
        {
          title: str,             # e.g. "EXPERIENCE"
          type: 'entries'|'flat', # entries = jobs/edu with dates; flat = skills/certs
          entries: [              # for type='entries'
            { role, company, date, location, bullets:[str], body:[str] }
          ],
          lines: [str],           # for type='flat'
        }
      ]
    }
    """
    raw_lines = [l.rstrip() for l in text.split('\n')]
    out = {'name': '', 'contact': [], 'sections': []}

    i = 0
    # Skip leading blanks → name
    while i < len(raw_lines) and not raw_lines[i].strip():
        i += 1
    if i < len(raw_lines):
        out['name'] = raw_lines[i].strip()
        i += 1

    # Contact block — until first section header
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if not line:
            i += 1
            continue
        if SECTION_RE.match(line):
            break
        # Flatten separator chars, keep each contact item separate
        parts = re.split(r'\s*[|·•]\s*', line)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # Skip label-only lines like "PHONE:" or "EMAIL:"
            if re.match(r'^(phone|email|address|linkedin|website|url)\s*:?\s*$', p, re.I):
                i += 1
                continue
            # Strip inline labels like "PHONE: 206-483" → "206-483"
            p = re.sub(r'^(phone|email|linkedin|url|address)\s*:\s*', '', p, flags=re.I).strip()
            if p:
                out['contact'].append(p)
        i += 1

    # Sections
    cur_sec = None
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if SECTION_RE.match(line):
            if cur_sec:
                out['sections'].append(_finalize_section(cur_sec))
            cur_sec = {'title': line.upper().rstrip(':'), '_lines': []}
        elif cur_sec is not None:
            cur_sec['_lines'].append(raw_lines[i])
        i += 1
    if cur_sec:
        out['sections'].append(_finalize_section(cur_sec))

    return out


def _finalize_section(sec: dict) -> dict:
    lines = sec['_lines']
    title = sec['title']

    # Decide section type
    is_entry_section = bool(re.search(
        r'^(EXPERIENCE|WORK|PROFESSIONAL EXPERIENCE|EMPLOYMENT|EDUCATION|ACADEMIC|PROJECTS?)',
        title, re.I
    ))

    if is_entry_section:
        entries = _parse_entries(lines)
        return {'title': title, 'type': 'entries', 'entries': entries}
    else:
        flat = [l.strip() for l in lines if l.strip()]
        return {'title': title, 'type': 'flat', 'lines': flat}


def _parse_entries(lines) -> list:
    """Parse experience/education lines into structured entries."""
    entries = []
    cur = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Bullet point → always attach to current entry
        bm = BULLET_RE.match(line)
        if bm:
            if cur is None:
                cur = _new_entry()
            cur['bullets'].append(bm.group(1).strip())
            continue

        # Sub-detail lines (GPA, coursework, major, etc.)
        # Always attach to current entry, never start a new one
        is_subdetail = bool(re.match(
            r'^(gpa|cgpa|grade|cumulative|relevant coursework|coursework|'
            r'major:|concentration:|minor:|honors|dean|cum laude|'
            r'thesis:|dissertation:|member of)',
            line, re.I
        ))
        if is_subdetail and cur is not None:
            cur['body'].append(line)
            continue

        # Detect entry header line
        has_date = bool(DATE_RE.search(line))
        is_short = len(line) < 100 and not line.endswith('.')
        looks_like_header = is_short and (has_date or re.search(
            r'\b(engineer|developer|analyst|manager|intern|specialist|'
            r'staff|assistant|coordinator|director|lead|researcher|'
            r'scientist|designer|consultant|officer|architect|'
            r'university|college|institute|bachelor|master|b\.s|m\.s|m\.eng|'
            r'inc\.|llc|corp|ltd|company|center|school|academy|'
            r'google|amazon|microsoft|apple|meta|netflix|panda|factory|'
            r'southeast|sunderland|islington|semo|cloudfactory|fleetpanda)\b',
            line, re.I
        ))

        if looks_like_header:
            if cur:
                entries.append(cur)
            cur = _new_entry()
            # Extract date from line
            dm = DATE_RE.search(line)
            if dm:
                cur['date'] = line[dm.start():dm.end()].strip()
                rest = (line[:dm.start()] + line[dm.end():]).strip().strip('–—|-').strip()
            else:
                cur['date'] = ''
                rest = line

            # Split "Role — Company   Location"
            sep = re.split(r'\s*[–—|]\s*|\s{3,}', rest, maxsplit=1)
            cur['role'] = sep[0].strip()
            if len(sep) > 1:
                loc_split = re.split(r',\s*', sep[1], maxsplit=1)
                cur['company'] = loc_split[0].strip()
                cur['location'] = loc_split[1].strip() if len(loc_split) > 1 else ''
        else:
            # Any other line → attach as body to current entry
            if cur is None:
                cur = _new_entry()
            cur['body'].append(line)

    if cur:
        entries.append(cur)

    return entries


def _new_entry():
    return {'role': '', 'company': '', 'location': '', 'date': '',
            'bullets': [], 'body': []}


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: Render templates
# ══════════════════════════════════════════════════════════════════════════

def _make_doc(buf, tm=None, bm=None):
    return SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=LM, rightMargin=RM,
        topMargin=tm or TM, bottomMargin=bm or BM
    )


def _role_date_row(role_text, company_text, date_text, role_s, company_s, date_s):
    """Returns a Table with role+company left, date right."""
    left = []
    if role_text:
        left.append(Paragraph(role_text, role_s))
    if company_text:
        left.append(Paragraph(company_text, company_s))

    right = Paragraph(date_text, date_s) if date_text else Paragraph('', date_s)

    # Stack left items in a nested table
    if len(left) == 0:
        left_cell = Paragraph('', role_s)
    elif len(left) == 1:
        left_cell = left[0]
    else:
        inner = Table([[item] for item in left], colWidths=[CW * 0.68])
        inner.setStyle(TableStyle([
            ('LEFTPADDING',(0,0),(-1,-1),0),
            ('RIGHTPADDING',(0,0),(-1,-1),0),
            ('TOPPADDING',(0,0),(-1,-1),0),
            ('BOTTOMPADDING',(0,0),(-1,-1),1),
        ]))
        left_cell = inner

    t = Table([[left_cell, right]], colWidths=[CW * 0.70, CW * 0.30])
    t.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),0),
        ('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    return t


def _render_section_content(sec, styles):
    """Render a section's content into a list of flowables."""
    role_s, company_s, date_s, bullet_s, body_s = (
        styles['role'], styles['company'], styles['date'],
        styles['bullet'], styles['body']
    )
    # Sub-detail style (GPA, coursework) — slightly smaller, indented
    from reportlab.lib.styles import ParagraphStyle
    sub_detail_s = ParagraphStyle(
        'sd',
        parent=body_s,
        fontSize=body_s.fontSize - 0.5,
        textColor=company_s.textColor,
        leftIndent=0,
        spaceAfter=1,
        leading=12,
    )

    items = []

    if sec['type'] == 'entries':
        for e in sec['entries']:
            entry_items = []
            if e['role'] or e['company'] or e['date']:
                row = _role_date_row(
                    e['role'], e['company'], e['date'],
                    role_s, company_s, date_s
                )
                entry_items.append(row)
            if e['location']:
                entry_items.append(Paragraph(e['location'], company_s))
            for b in e['body']:
                entry_items.append(Paragraph(b, sub_detail_s))
            for b in e['bullets']:
                entry_items.append(Paragraph(f'• {b}', bullet_s))
            entry_items.append(Spacer(1, 4))
            items.extend(entry_items)
    else:
        for line in sec['lines']:
            bm = BULLET_RE.match(line)
            if bm:
                items.append(Paragraph(f'• {bm.group(1)}', bullet_s))
            else:
                items.append(Paragraph(line, body_s))
        items.append(Spacer(1, 2))

    return items


# ── CLASSIC ────────────────────────────────────────────────────────────────
def build_classic(data: dict) -> bytes:
    buf = BytesIO()
    doc = _make_doc(buf)

    BK = colors.HexColor('#111111')
    GR = colors.HexColor('#2d2d2d')
    MD = colors.HexColor('#555555')
    LG = colors.HexColor('#777777')

    def S(name, **kw):
        d = dict(fontName='Helvetica', fontSize=10, textColor=GR,
                 leading=14, spaceAfter=0, spaceBefore=0)
        d.update(kw)
        return ParagraphStyle(name, **d)

    styles = {
        'role':    S('ro', fontName='Helvetica-Bold', fontSize=10,
                     textColor=BK, spaceBefore=5, leading=14),
        'company': S('co', fontName='Helvetica-Oblique', fontSize=9.5,
                     textColor=MD, leading=13),
        'date':    S('da', fontSize=9, textColor=LG,
                     alignment=TA_RIGHT, leading=14),
        'bullet':  S('bu', fontSize=9.5, textColor=GR,
                     leftIndent=14, firstLineIndent=-9,
                     spaceAfter=2, leading=13),
        'body':    S('bo', fontSize=9.5, textColor=GR,
                     spaceAfter=2, leading=13),
    }

    name_s = S('na', fontName='Helvetica-Bold', fontSize=22,
               textColor=BK, alignment=TA_CENTER, leading=26, spaceAfter=3)
    con_s  = S('cn', fontSize=9, textColor=LG,
               alignment=TA_CENTER, leading=13, spaceAfter=8)
    sec_s  = S('sc', fontName='Helvetica-Bold', fontSize=10,
               textColor=BK, spaceBefore=10, spaceAfter=3,
               letterSpacing=0.5, leading=14)

    story = []
    story.append(Paragraph(data['name'], name_s))

    contact = data['contact']
    if contact:
        # Max 2 lines, 4 items per line
        story.append(Paragraph('  |  '.join(contact[:4]), con_s))
        if len(contact) > 4:
            story.append(Paragraph('  |  '.join(contact[4:]), con_s))

    story.append(HRFlowable(width='100%', thickness=1.5,
                            color=BK, spaceAfter=6))

    for sec in data['sections']:
        block = []
        block.append(Paragraph(sec['title'], sec_s))
        block.append(HRFlowable(width='100%', thickness=0.5,
                                color=colors.HexColor('#bbbbbb'), spaceAfter=4))
        block.extend(_render_section_content(sec, styles))
        # Keep header+rule together, but let content flow naturally
        story.append(KeepTogether(block[:2]))
        for item in block[2:]:
            story.append(item)

    doc.build(story)
    return buf.getvalue()


# ── MODERN ─────────────────────────────────────────────────────────────────
def build_modern(data: dict, accent='#1d4ed8') -> bytes:
    buf = BytesIO()
    doc = _make_doc(buf)

    AC = colors.HexColor(accent)
    BK = colors.HexColor('#111827')
    GR = colors.HexColor('#374151')
    MD = colors.HexColor('#6b7280')
    LG = colors.HexColor('#9ca3af')

    def S(name, **kw):
        d = dict(fontName='Helvetica', fontSize=10, textColor=GR,
                 leading=14, spaceAfter=0, spaceBefore=0)
        d.update(kw)
        return ParagraphStyle(name, **d)

    styles = {
        'role':    S('ro', fontName='Helvetica-Bold', fontSize=10,
                     textColor=BK, spaceBefore=5, leading=14),
        'company': S('co', fontName='Helvetica-Oblique', fontSize=9.5,
                     textColor=MD, leading=13),
        'date':    S('da', fontSize=9, textColor=LG,
                     alignment=TA_RIGHT, leading=14),
        'bullet':  S('bu', fontSize=9.5, textColor=GR,
                     leftIndent=14, firstLineIndent=-9,
                     spaceAfter=2, leading=13),
        'body':    S('bo', fontSize=9.5, textColor=GR,
                     spaceAfter=2, leading=13),
    }

    name_s = S('na', fontName='Helvetica-Bold', fontSize=23,
               textColor=BK, leading=27, spaceAfter=2)
    con_s  = S('cn', fontSize=9, textColor=MD, leading=13, spaceAfter=6)
    sec_s  = S('sc', fontName='Helvetica-Bold', fontSize=9,
               textColor=AC, spaceBefore=12, spaceAfter=3,
               letterSpacing=1.5, leading=13)

    story = []
    story.append(Paragraph(data['name'], name_s))

    contact = data['contact']
    if contact:
        story.append(Paragraph('  |  '.join(contact[:5]), con_s))

    story.append(HRFlowable(width='100%', thickness=2.5,
                            color=AC, spaceAfter=8))

    for sec in data['sections']:
        block = []
        block.append(Paragraph(sec['title'].upper(), sec_s))
        block.append(HRFlowable(width='100%', thickness=0.5,
                                color=colors.HexColor('#e5e7eb'), spaceAfter=4))
        block.extend(_render_section_content(sec, styles))
        # Keep header+rule together, but let content flow naturally
        story.append(KeepTogether(block[:2]))
        for item in block[2:]:
            story.append(item)

    doc.build(story)
    return buf.getvalue()


# ── EXECUTIVE ──────────────────────────────────────────────────────────────
def build_executive(data: dict) -> bytes:
    buf = BytesIO()
    doc = _make_doc(buf, tm=0.5*inch)

    DARK = colors.HexColor('#0f172a')
    BK   = colors.HexColor('#1e293b')
    GR   = colors.HexColor('#334155')
    MD   = colors.HexColor('#64748b')
    LG   = colors.HexColor('#94a3b8')
    WH   = colors.white

    def S(name, **kw):
        d = dict(fontName='Helvetica', fontSize=10, textColor=GR,
                 leading=14, spaceAfter=0, spaceBefore=0)
        d.update(kw)
        return ParagraphStyle(name, **d)

    styles = {
        'role':    S('ro', fontName='Helvetica-Bold', fontSize=10,
                     textColor=BK, spaceBefore=5, leading=14),
        'company': S('co', fontName='Helvetica-Oblique', fontSize=9.5,
                     textColor=MD, leading=13),
        'date':    S('da', fontSize=9, textColor=LG,
                     alignment=TA_RIGHT, leading=14),
        'bullet':  S('bu', fontSize=9.5, textColor=GR,
                     leftIndent=14, firstLineIndent=-9,
                     spaceAfter=2, leading=13),
        'body':    S('bo', fontSize=9.5, textColor=GR,
                     spaceAfter=2, leading=13),
    }

    sec_s = S('sc', fontName='Helvetica-Bold', fontSize=9,
              textColor=DARK, spaceBefore=12, spaceAfter=3,
              letterSpacing=2, leading=13)

    story = []

    # Dark header
    contact = data.get('contact', [])
    flat_items = [c.strip() for c in contact[:5] if c.strip()]
    flat = ' | '.join(flat_items)
    if len(flat) > 220:
        flat = flat[:220].rsplit(' ', 1)[0] + '...'

    # Ensure header width fits in all frame layouts
    hdr_width = min(CW - 2, 499.2)

    hdr = Table(
        [[Paragraph(f'<font size="21"><b>{data.get("name", "")}</b></font>',
                    ParagraphStyle('hn', fontName='Helvetica-Bold', fontSize=21,
                                   textColor=WH, leading=25))],
         [Paragraph(flat,
                    ParagraphStyle('hc', fontName='Helvetica', fontSize=8.5,
                                   textColor=colors.HexColor('#94a3b8'),
                                   leading=12,
                                   wordWrap='CJK'))]],
        colWidths=[hdr_width]
    )
    hdr.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), DARK),
        ('LEFTPADDING',(0,0),(-1,-1), LM),
        ('RIGHTPADDING',(0,0),(-1,-1), RM),
        ('TOPPADDING',(0,0),(0,0), 14),
        ('BOTTOMPADDING',(0,-1),(-1,-1), 14),
        ('TOPPADDING',(0,1),(-1,-1), 3),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 10))

    for sec in data['sections']:
        block = []
        block.append(Paragraph(sec['title'].upper(), sec_s))
        block.append(HRFlowable(width='100%', thickness=1.5,
                                color=DARK, spaceAfter=5))
        block.extend(_render_section_content(sec, styles))
        # Keep header+rule together, but let content flow naturally
        story.append(KeepTogether(block[:2]))
        for item in block[2:]:
            story.append(item)

    doc.build(story)
    return buf.getvalue()


# ── Minimal = Modern with green accent ─────────────────────────────────────
def build_minimal(data: dict) -> bytes:
    return build_modern(data, accent='#059669')


# ── Registry ───────────────────────────────────────────────────────────────
TEMPLATES = {
    'classic':   ('Classic',   'Traditional black & white — highest ATS pass rate', build_classic),
    'modern':    ('Modern',    'Blue accents, contemporary — great for tech roles',  build_modern),
    'minimal':   ('Minimal',   'Green accents, clean and sharp',                     build_minimal),
    'executive': ('Executive', 'Dark header banner — perfect for senior roles',      build_executive),
}


def generate_resume_pdf(resume_text: str, template: str = 'classic') -> bytes:
    data    = parse_resume(resume_text)
    builder = TEMPLATES.get(template, TEMPLATES['classic'])[2]
    return builder(data)
