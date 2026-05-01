"""
report.py — Generate professional PDF analysis reports using ReportLab
"""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Brand colors ──────────────────────────────────────────────────────────
SEMO_RED   = colors.HexColor('#c8102e')
SEMO_BLACK = colors.HexColor('#1a1a1a')
GRAY_LIGHT = colors.HexColor('#f5f5f5')
GRAY_MID   = colors.HexColor('#888888')
GREEN      = colors.HexColor('#198754')
AMBER      = colors.HexColor('#fd7e14')
RED_SOFT   = colors.HexColor('#dc3545')


def score_color(score: int):
    if score >= 70:
        return GREEN
    if score >= 40:
        return AMBER
    return RED_SOFT


def generate_pdf_report(results: dict, user_name: str = "Student") -> bytes:
    """
    Build a PDF report from analysis results dict.
    Returns raw PDF bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Custom styles ─────────────────────────────────────────────────────
    title_style = ParagraphStyle('Title', parent=styles['Title'],
        fontSize=22, textColor=SEMO_RED, spaceAfter=4, alignment=TA_LEFT)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
        fontSize=11, textColor=GRAY_MID, spaceAfter=16)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
        fontSize=13, textColor=SEMO_BLACK, spaceBefore=18, spaceAfter=8,
        borderPad=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, leading=15, textColor=SEMO_BLACK)
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=9, textColor=GRAY_MID, leading=13)
    warning_style = ParagraphStyle('Warning', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#856404'),
        backColor=colors.HexColor('#fff3cd'), leading=14,
        leftIndent=8, rightIndent=8, spaceBefore=8, spaceAfter=8, borderPad=6)

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("ResumeForge", title_style))
    story.append(Paragraph("ATS Analysis Report — Southeast Missouri State University", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=SEMO_RED, spaceAfter=12))

    # Meta row
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    meta_data = [
        ["Prepared for:", user_name, "Date:", now],
        ["Resume words:", str(results.get('resume_word_count', 0)),
         "Job words:", str(results.get('job_word_count', 0))],
    ]
    meta_table = Table(meta_data, colWidths=[1.2*inch, 2.5*inch, 1*inch, 2.3*inch])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), GRAY_MID),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # ── Score section ─────────────────────────────────────────────────────
    score = results.get('score', 0)
    score_label = "Strong Match" if score >= 70 else "Moderate Match" if score >= 40 else "Needs Work"
    sc = score_color(score)

    score_data = [[
        Paragraph(f'<font size="36" color="{sc.hexval()}"><b>{score}%</b></font>', styles['Normal']),
        Paragraph(f'<b>{score_label}</b><br/><font size="9" color="#888888">'
                  f'Matched {results.get("matched_count",0)} of {results.get("total_job_keywords",0)} keywords</font>',
                  body_style),
    ]]
    score_table = Table(score_data, colWidths=[1.5*inch, 5.5*inch])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 8))

    # ── Sub-scores ────────────────────────────────────────────────────────
    sub_scores = results.get('sub_scores', {})
    label_map = [
        ("hard_skills", "Hard Skills"),
        ("soft_skills", "Soft Skills"),
        ("tools", "Tools"),
        ("certifications", "Certifications"),
    ]
    sub_row = []
    for key, label in label_map:
        val = sub_scores.get(key)
        if val is not None:
            sub_row.append(
                Paragraph(f'<b>{label}</b><br/>'
                          f'<font size="14" color="{score_color(val).hexval()}"><b>{val}%</b></font>',
                          ParagraphStyle('sub', parent=styles['Normal'], fontSize=9,
                                         alignment=TA_CENTER, leading=16))
            )
        else:
            sub_row.append(
                Paragraph(f'<b>{label}</b><br/><font size="11" color="#aaaaaa">N/A</font>',
                          ParagraphStyle('sub', parent=styles['Normal'], fontSize=9,
                                         alignment=TA_CENTER, leading=16))
            )
    sub_table = Table([sub_row], colWidths=[1.75*inch]*4)
    sub_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#eeeeee')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 4))

    # Detected sections
    sections = results.get('sections_found', [])
    if sections:
        story.append(Paragraph(
            f'<font size="9" color="#888888">Resume sections detected: '
            f'{", ".join(s.title() for s in sections)}</font>',
            body_style))

    # ── Matched keywords ──────────────────────────────────────────────────
    story.append(Paragraph("✓ Matched Keywords", section_style))
    matched = results.get('matched', [])
    if matched:
        # Wrap in colored badges (simulate with a table of small cells)
        cols = 6
        rows = [matched[i:i+cols] for i in range(0, len(matched), cols)]
        badge_data = []
        for row in rows:
            badge_row = []
            for kw in row:
                badge_row.append(
                    Paragraph(f'<font size="8" color="#0a5e0a">{kw}</font>',
                               ParagraphStyle('badge', parent=styles['Normal'],
                                              alignment=TA_CENTER, leading=11))
                )
            while len(badge_row) < cols:
                badge_row.append(Paragraph('', body_style))
            badge_data.append(badge_row)

        badge_table = Table(badge_data, colWidths=[1.17*inch]*cols)
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#d1e7dd')),
            ('BOX', (0,0), (-1,-1), 0.3, colors.HexColor('#a3cfbb')),
            ('INNERGRID', (0,0), (-1,-1), 0.3, colors.white),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(badge_table)
    else:
        story.append(Paragraph("No matching keywords found.", small_style))

    # ── Missing keywords ──────────────────────────────────────────────────
    story.append(Paragraph("✗ Missing Keywords", section_style))
    missing = results.get('missing', [])
    if missing:
        cols = 6
        rows = [missing[i:i+cols] for i in range(0, len(missing), cols)]
        badge_data = []
        for row in rows:
            badge_row = []
            for kw in row:
                badge_row.append(
                    Paragraph(f'<font size="8" color="#842029">{kw}</font>',
                               ParagraphStyle('badge2', parent=styles['Normal'],
                                              alignment=TA_CENTER, leading=11))
                )
            while len(badge_row) < cols:
                badge_row.append(Paragraph('', body_style))
            badge_data.append(badge_row)

        badge_table = Table(badge_data, colWidths=[1.17*inch]*cols)
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8d7da')),
            ('BOX', (0,0), (-1,-1), 0.3, colors.HexColor('#f1aeb5')),
            ('INNERGRID', (0,0), (-1,-1), 0.3, colors.white),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(badge_table)
    else:
        story.append(Paragraph("No missing keywords — perfect match!", body_style))

    # ── Improvement suggestions ───────────────────────────────────────────
    story.append(Paragraph("Improvement Suggestions", section_style))
    suggestions = results.get('suggestions', [])
    cat_labels = {
        "hard_skill": "Hard Skill", "soft_skill": "Soft Skill",
        "tool": "Tool", "certification": "Certification", "other": "Other"
    }
    if suggestions:
        sug_data = [["Keyword", "Category", "Suggested Placement"]]
        for s in suggestions:
            sug_data.append([
                s['keyword'],
                cat_labels.get(s['category'], s['category']),
                s['placement'],
            ])
        sug_table = Table(sug_data, colWidths=[1.6*inch, 1.2*inch, 4.2*inch])
        sug_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), SEMO_BLACK),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GRAY_LIGHT]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#cccccc')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(sug_table)
    else:
        story.append(Paragraph("No suggestions — your resume looks great!", body_style))

    # ── Ethical notice ────────────────────────────────────────────────────
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "⚠ Ethical Notice: Only add keywords that honestly reflect your actual experience "
        "and skills. Do not fabricate credentials, work history, or certifications. "
        "ResumeForge helps you present genuine qualifications more effectively.",
        warning_style
    ))

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_MID))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by ResumeForge · SEMO CS Capstone 2026 · "
        "Team: Kamal Batala, Reshan Dulal, Jackson Dickinson · "
        f"Advisor: Dr. Reshmi Mitra",
        ParagraphStyle('footer', parent=styles['Normal'], fontSize=8,
                       textColor=GRAY_MID, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buffer.getvalue()
