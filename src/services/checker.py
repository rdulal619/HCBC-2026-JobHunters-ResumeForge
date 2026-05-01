"""
checker.py — ResumeForge resume quality checker
Stricter, more meaningful scoring based on real ATS criteria.
Scores reflect genuine resume quality — not inflated pass/fail checks.
"""

import re
from collections import Counter

# ── Patterns ──────────────────────────────────────────────────────────────
EMAIL_RE    = re.compile(r'[\w.+-]+@[\w-]+\.\w+')
PHONE_RE    = re.compile(r'[\+\(]?[\d\s\-\(\)\.]{7,}')
LINKEDIN_RE = re.compile(r'linkedin\.com/in/[\w\-]+', re.I)
GITHUB_RE   = re.compile(r'github\.com/[\w\-]+', re.I)
DATE_RE     = re.compile(
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|'
    r'march|april|june|july|august|september|october|november|december|\d{4})\b',
    re.I
)

# Strict number/metric pattern — must be a real achievement metric
NUMBER_RE = re.compile(
    r'(\d+\s*%'                          # percentages: 40%, 15 %
    r'|\d+\s*x\b'                        # multipliers: 3x
    r'|\$\s*\d+'                         # dollar amounts
    r'|\d+\+?\s*(users|customers|clients|students|engineers|'
    r'tickets|issues|requests|transactions|'
    r'million|thousand|k\b|m\b)'         # counts with units
    r'|\d+\s*(ms|seconds|minutes|hours|days|weeks|months)\b'  # time
    r'|\b(doubled|tripled|halved)\b'     # qualitative multipliers
    r'|\bby\s+\d+'                       # "by 40", "by 3x"
    r')',
    re.I
)

BULLET_RE = re.compile(r'^[\•\-\*\–►▸▪]\s*(.+)', re.M)

SECTION_PATTERNS = {
    'experience':     re.compile(r'\b(experience|employment|work history|professional background)\b', re.I),
    'education':      re.compile(r'\b(education|academic|degree|university|college|school)\b', re.I),
    'skills':         re.compile(r'\b(skills?|technical skills?|competencies|expertise|proficiencies|technologies)\b', re.I),
    'summary':        re.compile(r'\b(summary|objective|profile|about me|overview|professional summary)\b', re.I),
    'projects':       re.compile(r'\b(projects?|portfolio|open source|personal projects?)\b', re.I),
    'certifications': re.compile(r'\b(certifications?|licenses?|credentials?|accreditations?)\b', re.I),
}

WEAK_PHRASES = [
    'responsible for', 'worked on', 'helped with', 'assisted with',
    'was involved in', 'participated in', 'contributed to',
    'duties included', 'tasks included', 'helped to',
]

STRONG_VERBS = {
    'developed','built','created','designed','implemented','engineered',
    'deployed','led','managed','optimized','improved','increased','reduced',
    'automated','delivered','maintained','resolved','enhanced','architected',
    'launched','established','streamlined','spearheaded','executed','drove',
    'coordinated','produced','achieved','generated','accelerated','transformed',
    'mentored','trained','analyzed','migrated','integrated','refactored',
    'scaled','secured','monitored','configured','administered','negotiated',
}

BUZZWORDS = [
    'hardworking', 'team player', 'go-getter', 'think outside the box',
    'synergy', 'passionate about', 'guru', 'ninja', 'rockstar',
    'thought leader', 'detail-oriented', 'self-starter',
    'results-driven', 'dynamic', 'motivated individual',
]

# Words that are legitimately repeated in tech resumes — don't penalize
TECH_STOP_WORDS = {
    'python', 'java', 'data', 'model', 'system', 'using', 'team',
    'project', 'code', 'service', 'application', 'software', 'user',
    'database', 'api', 'test', 'build', 'work', 'pipeline', 'cloud',
    'machine', 'learning', 'experience', 'skill', 'design', 'develop',
}


def _lines(text):
    return [l.strip() for l in text.split('\n') if l.strip()]


def _bullets(text):
    return BULLET_RE.findall(text)


def _detect_sections(text):
    found = {}
    for name, pat in SECTION_PATTERNS.items():
        if pat.search(text):
            found[name] = True
    return found


def _experience_bullets(text):
    """Get only bullets that are likely in experience/projects sections."""
    bullets = _bullets(text)
    # Filter out skill category lines and very short bullets
    return [b for b in bullets if len(b.split()) >= 5 
            and not re.match(r'^(languages|frameworks|tools|databases|skills|cloud|data|machine|devops|other|programming)', b, re.I)]


# ── CONTENT checks ────────────────────────────────────────────────────────

def check_ats_parse_rate(text):
    """
    Real ATS parse check — not just 'has text'.
    Checks for common ATS-breaking elements.
    """
    issues = []

    # Too short
    if len(text.split()) < 150:
        issues.append('Resume appears too short (under 150 words)')

    # Check for garbled text (encoding issues)
    garbled = len(re.findall(r'[^\x00-\x7F]', text)) / max(len(text), 1)
    if garbled > 0.05:
        issues.append('Possible encoding issues detected')

    # Check for missing key info
    if not re.search(r'[\w.+-]+@[\w-]+\.\w+', text):
        issues.append('No email found — ATS cannot contact you')

    if not re.search(r'\b(experience|education|skills)\b', text, re.I):
        issues.append('Missing standard section headers')

    score = max(30, 100 - len(issues) * 20)

    return {
        'status': 'pass' if not issues else 'fail',
        'detail': 'Resume parsed successfully with no issues.' if not issues
                  else f'{len(issues)} parsing issue(s) found: ' + '; '.join(issues),
        'issues': issues,
        'score': score,
    }


def check_quantify_impact(text):
    """
    Check what % of experience bullets have measurable impact.
    This is the most important check — scored strictly.
    """
    bullets = _experience_bullets(text)

    if not bullets:
        return {
            'status': 'warn',
            'detail': 'No bullet points detected. Use bullet points in your experience section.',
            'count': 0, 'flagged': [], 'total': 0,
            'score': 20,
        }

    quantified = []
    unquantified = []
    for b in bullets:
        if NUMBER_RE.search(b):
            quantified.append(b)
        else:
            unquantified.append(b)

    total = len(bullets)
    pct_quantified = len(quantified) / total if total else 0

    # Strict scoring: 100% quantified = 100, 50% = 60, 0% = 10
    if pct_quantified >= 0.80:
        score = 100
        status = 'pass'
    elif pct_quantified >= 0.60:
        score = 80
        status = 'warn'
    elif pct_quantified >= 0.40:
        score = 60
        status = 'warn'
    elif pct_quantified >= 0.20:
        score = 35
        status = 'fail'
    else:
        score = 10
        status = 'fail'

    return {
        'status': status,
        'count': len(unquantified),
        'total': total,
        'pct': int(pct_quantified * 100),
        'flagged': [b[:90] + ('...' if len(b) > 90 else '') for b in unquantified[:10]],
        'detail': f'{len(quantified)}/{total} bullets ({int(pct_quantified*100)}%) have measurable results.'
                  if pct_quantified > 0
                  else f'0/{total} bullets have measurable results. Add numbers, percentages, and metrics.',
        'score': score,
    }


def check_repetition(text):
    """
    Check for non-technical word repetition.
    Ignores legitimate tech terms.
    """
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text.lower())
    stop = {
        'with','that','this','have','from','they','will','your','been',
        'were','their','about','which','when','also','into','more','some',
        'what','than','then','them','these','there','using','used','while',
        'each','such','both','over','after','before','through','during',
        'within','across','between','against','without',
    }
    # Count only non-tech, non-stop words
    filtered = [w for w in words if w not in stop and w not in TECH_STOP_WORDS]
    freq = Counter(filtered)

    # Only flag if used 6+ times (stricter threshold)
    repeated = [(w, c) for w, c in freq.most_common(20) if c >= 6]
    count = len(repeated)

    return {
        'status': 'pass' if count == 0 else 'warn',
        'count': count,
        'repeated': repeated[:4],
        'detail': 'No problematic word repetition found.' if count == 0
                  else f'{count} word(s) overused: {", ".join(w for w,_ in repeated[:3])}. Use synonyms.',
        'score': 100 if count == 0 else max(65, 100 - count * 8),
    }


def check_spelling_grammar(text):
    """Check for weak phrases, buzzwords, passive voice."""
    issues = []
    text_lower = text.lower()

    # Weak phrases — each one costs points
    for phrase in WEAK_PHRASES:
        count = text_lower.count(phrase)
        if count > 0:
            issues.append(f'"{phrase}" ({count}x) — replace with action verbs')

    # Buzzwords
    for bw in BUZZWORDS:
        if bw in text_lower:
            issues.append(f'Buzzword: "{bw}"')

    # Passive voice
    passive = len(re.findall(r'\b(was|were|been|being)\s+\w+ed\b', text_lower))
    if passive > 3:
        issues.append(f'Passive voice used {passive} times — use active voice')

    count = len(issues)
    score = max(30, 100 - count * 15)

    return {
        'status': 'pass' if count == 0 else ('warn' if count <= 2 else 'fail'),
        'count': count,
        'issues': issues[:6],
        'detail': 'No weak phrases or buzzwords found.' if count == 0
                  else f'{count} phrasing issue(s) found.',
        'score': score,
    }


def check_action_verbs(text):
    """Check that bullets start with strong action verbs."""
    bullets = _experience_bullets(text)

    if not bullets:
        return {'status': 'warn', 'detail': 'No bullet points detected.', 'score': 30,
                'strong': 0, 'total': 0}

    strong_count = 0
    for b in bullets:
        first_word = b.split()[0].lower().rstrip('.,;:')
        if first_word in STRONG_VERBS:
            strong_count += 1

    total = len(bullets)
    pct = int(strong_count / total * 100) if total else 0

    if pct >= 80:
        score, status = 100, 'pass'
    elif pct >= 60:
        score, status = 75, 'warn'
    elif pct >= 40:
        score, status = 50, 'warn'
    else:
        score, status = 25, 'fail'

    return {
        'status': status,
        'strong': strong_count,
        'total': total,
        'pct': pct,
        'detail': f'{strong_count}/{total} bullets ({pct}%) start with strong action verbs.',
        'score': score,
    }


# ── SECTIONS checks ───────────────────────────────────────────────────────

def check_essential_sections(text):
    sections = _detect_sections(text)
    required = ['experience', 'education', 'skills']
    found    = [s for s in required if s in sections]
    missing  = [s for s in required if s not in sections]

    score = int(len(found) / len(required) * 100)
    # Missing experience is a hard hit
    if 'experience' in missing:
        score = min(score, 30)

    return {
        'status': 'pass' if not missing else 'fail',
        'found': found,
        'missing': missing,
        'all_sections': list(sections.keys()),
        'detail': f'Found: {", ".join(s.title() for s in found)}.' +
                  (f' Missing: {", ".join(s.title() for s in missing)}.' if missing else ''),
        'score': score,
    }


def check_contact_info(text):
    has_email    = bool(EMAIL_RE.search(text))
    has_phone    = bool(PHONE_RE.search(text))
    has_linkedin = bool(LINKEDIN_RE.search(text))
    has_github   = bool(GITHUB_RE.search(text))

    email_match = EMAIL_RE.search(text)
    email_quality = 'good'
    if email_match:
        local = email_match.group().split('@')[0].lower()
        if re.search(r'\d{3,}', local):
            email_quality = 'unprofessional'

    details = []
    if has_email:
        details.append(f'✓ Email: {email_match.group()}')
        if email_quality == 'unprofessional':
            details.append('⚠ Email has many numbers — consider firstname.lastname format')
    else:
        details.append('✗ No email found — critical missing info')

    if has_phone:  details.append('✓ Phone number found')
    else:          details.append('✗ No phone number — add it')
    if has_linkedin: details.append('✓ LinkedIn profile found')
    else:            details.append('○ No LinkedIn URL — strongly recommended')
    if has_github:   details.append('✓ GitHub profile found')
    else:            details.append('○ No GitHub link — recommended for tech roles')

    # Strict scoring: email + phone are must-haves
    score = 0
    if has_email: score += 35
    if has_phone: score += 35
    if has_linkedin: score += 20
    if has_github: score += 10

    return {
        'status': 'pass' if has_email and has_phone else 'fail',
        'has_email': has_email, 'has_phone': has_phone,
        'has_linkedin': has_linkedin, 'has_github': has_github,
        'email_quality': email_quality,
        'details': details,
        'score': score,
    }


def check_summary(text):
    sections = _detect_sections(text)
    has_summary = 'summary' in sections

    # Check if summary has substance (3+ sentences or 50+ words)
    summary_match = re.search(
        r'(summary|objective|profile|about me|overview)[:\s]*\n(.{80,})',
        text, re.I | re.DOTALL
    )
    substantial = bool(summary_match)

    if has_summary and substantial:
        score, status = 100, 'pass'
    elif has_summary:
        score, status = 60, 'warn'
    else:
        score, status = 0, 'warn'

    return {
        'status': status,
        'has_summary': has_summary,
        'substantial': substantial,
        'detail': 'Professional summary found.' if has_summary
                  else 'No summary section. A 2-3 sentence professional summary significantly helps recruiters.',
        'score': score,
    }


# ── ATS ESSENTIALS checks ─────────────────────────────────────────────────

def check_resume_length(text):
    words = len(text.split())
    est_pages = round(words / 400, 1)

    if words < 200:
        status, detail, score = 'fail', f'Too short ({words} words, ~{est_pages}p). Add more detail.', 20
    elif words < 300:
        status, detail, score = 'warn', f'Slightly short ({words} words). Expand experience bullets.', 60
    elif words > 1400:
        status, detail, score = 'warn', f'May be too long (~{est_pages} pages). Aim for 1-2 pages.', 65
    elif words > 1000:
        status, detail, score = 'pass', f'{words} words (~{est_pages} page(s)). Good length.', 90
    else:
        status, detail, score = 'pass', f'{words} words (~{est_pages} page(s)). Good length.', 100

    return {'status': status, 'detail': detail, 'words': words, 'score': score}


def check_dates(text):
    date_matches = DATE_RE.findall(text)
    has_dates = len(date_matches) >= 2
    has_current = bool(re.search(r'\b(present|current|now)\b', text, re.I))

    # Check date format consistency
    month_year = len(re.findall(
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}\b',
        text, re.I
    ))

    score = 100 if has_dates else 40
    return {
        'status': 'pass' if has_dates else 'warn',
        'detail': 'Employment dates detected.' if has_dates
                  else 'No clear dates found. Add month/year ranges to your experience.',
        'has_current': has_current,
        'month_year_count': month_year,
        'score': score,
    }


def check_file_type():
    return {
        'status': 'pass',
        'detail': 'File uploaded successfully and parsed.',
        'score': 100,
    }


def check_active_voice(text):
    passive = len(re.findall(r'\b(was|were|been|being)\s+\w+ed\b', text.lower()))
    if passive == 0:
        score, status = 100, 'pass'
    elif passive <= 2:
        score, status = 85, 'pass'
    elif passive <= 4:
        score, status = 65, 'warn'
    else:
        score, status = 40, 'fail'

    return {
        'status': status,
        'count': passive,
        'detail': 'Good use of active voice.' if passive <= 2
                  else f'{passive} passive voice constructions. Use active verbs for stronger impact.',
        'score': score,
    }


# ── STYLE checks ──────────────────────────────────────────────────────────

def check_bullet_length(text):
    bullets = _experience_bullets(text)
    long_bullets = [b for b in bullets if len(b.split()) > 35]
    short_bullets = [b for b in bullets if len(b.split()) < 5]
    count = len(long_bullets)

    if count == 0:
        score, status = 100, 'pass'
    elif count <= 2:
        score, status = 75, 'warn'
    else:
        score, status = 50, 'fail'

    return {
        'status': status,
        'count': count,
        'detail': 'Bullet point lengths look good.' if count == 0
                  else f'{count} bullet(s) are too long (>35 words). Keep bullets concise.',
        'flagged': [b[:80] + '...' for b in long_bullets[:3]],
        'score': score,
    }


def check_email_professionalism(text):
    email_match = EMAIL_RE.search(text)
    if not email_match:
        return {'status': 'warn', 'detail': 'No email found.', 'score': 0}

    email = email_match.group()
    local = email.split('@')[0].lower()
    bad = bool(re.search(r'\d{4,}', local))  # 4+ digits = unprofessional

    return {
        'status': 'warn' if bad else 'pass',
        'email': email,
        'detail': f'"{email}" has many numbers — use firstname.lastname format.' if bad
                  else f'"{email}" looks professional.',
        'score': 50 if bad else 100,
    }


# ── MASTER checker ────────────────────────────────────────────────────────

def check_resume(text: str) -> dict:
    # Content
    ats_parse    = check_ats_parse_rate(text)
    quantify     = check_quantify_impact(text)
    repetition   = check_repetition(text)
    spelling     = check_spelling_grammar(text)
    action_verbs = check_action_verbs(text)

    # Sections
    essential = check_essential_sections(text)
    contact   = check_contact_info(text)
    summary   = check_summary(text)

    # ATS Essentials
    length       = check_resume_length(text)
    dates        = check_dates(text)
    file_type    = check_file_type()
    active_voice = check_active_voice(text)

    # Style
    bullet_len = check_bullet_length(text)
    email_prof = check_email_professionalism(text)

    # ── Category scores (stricter weights) ──────────────────────────────
    # Content: quantify impact is the biggest driver (real ATS tools agree)
    content_score = int(
        ats_parse['score']    * 0.15 +
        quantify['score']     * 0.40 +   # Most important
        action_verbs['score'] * 0.20 +   # Second most important
        spelling['score']     * 0.15 +
        repetition['score']   * 0.10
    )

    sections_score = int(
        essential['score'] * 0.50 +
        contact['score']   * 0.30 +
        summary['score']   * 0.20
    )

    ats_score = int(
        length['score']       * 0.30 +
        dates['score']        * 0.30 +
        file_type['score']    * 0.20 +
        active_voice['score'] * 0.20
    )

    style_score = int(
        bullet_len['score'] * 0.60 +
        email_prof['score'] * 0.40
    )

    # Overall — content is king
    overall = int(
        content_score  * 0.45 +
        sections_score * 0.30 +
        ats_score      * 0.15 +
        style_score    * 0.10
    )

    def is_issue(check):
        return check.get('status') in ('fail', 'warn')

    content_issues  = sum(1 for c in [ats_parse, quantify, repetition, spelling, action_verbs] if is_issue(c))
    sections_issues = sum(1 for c in [essential, contact, summary] if is_issue(c))
    ats_issues      = sum(1 for c in [length, dates, file_type, active_voice] if is_issue(c))
    style_issues    = sum(1 for c in [bullet_len, email_prof] if is_issue(c))
    total_issues    = content_issues + sections_issues + ats_issues + style_issues

    return {
        'overall':         overall,
        'total_issues':    total_issues,
        'content_score':   content_score,
        'sections_score':  sections_score,
        'ats_score':       ats_score,
        'style_score':     style_score,
        'content_issues':  content_issues,
        'sections_issues': sections_issues,
        'ats_issues':      ats_issues,
        'style_issues':    style_issues,
        'ats_parse':    ats_parse,
        'quantify':     quantify,
        'repetition':   repetition,
        'spelling':     spelling,
        'action_verbs': action_verbs,
        'essential':    essential,
        'contact':      contact,
        'summary':      summary,
        'length':       length,
        'dates':        dates,
        'file_type':    file_type,
        'active_voice': active_voice,
        'bullet_len':   bullet_len,
        'email_prof':   email_prof,
        'tailoring':    None,
    }
