"""
analyzer.py — ResumeForge NLP engine
Full Jobscan-style analysis: keyword matching, section checks,
searchability, recruiter tips, skills comparison table
"""

import re
import math
from collections import defaultdict, Counter

SYNONYMS = {
    "js": "javascript", "javascript": "javascript",
    "ts": "typescript", "typescript": "typescript",
    "py": "python", "python": "python",
    "c++": "cplusplus", "cpp": "cplusplus", "c#": "csharp",
    "golang": "go",
    "reactjs": "react", "react.js": "react",
    "vuejs": "vue", "vue.js": "vue",
    "nodejs": "node", "node.js": "node", "nord.js": "node",
    "expressjs": "express", "express.js": "express",
    "nextjs": "nextjs", "next.js": "nextjs",
    "postgresql": "postgres", "mongo": "mongodb",
    "mssql": "sqlserver", "sql server": "sqlserver",
    "amazon web services": "aws",
    "google cloud": "gcp", "microsoft azure": "azure",
    "k8s": "kubernetes",
    "ci/cd": "cicd", "ci cd": "cicd",
    "ml": "machine learning", "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "team player": "teamwork", "team work": "teamwork",
    "problem solving": "problem solving",
    "problem-solving": "problem solving",
    "detail-oriented": "detail oriented",
    "self-motivated": "self motivated",
    "ms office": "microsoft office",
    "github": "git", "gitlab": "git",
    "scrum": "agile", "kanban": "agile",
    "restful": "rest", "rest api": "rest",
    "graphql": "graphql", "graph ql": "graphql",
    "aws": "aws", "gcp": "gcp", "azure": "azure",
    "docker": "docker", "kubernetes": "kubernetes",
    "jenkins": "jenkins", "jira": "jira",
    "linux": "linux", "bash": "bash",
    "redis": "redis", "mongodb": "mongodb",
    "react": "react", "angular": "angular", "vue": "vue",
    "node": "node", "express": "express",
    "java": "java", "python": "python",
    "sql": "sql", "nosql": "nosql",
    "rest": "rest", "api": "api",
    "git": "git", "agile": "agile",
    "postgres": "postgres",
    "tensorflow": "tensorflow", "pytorch": "pytorch",
    "pandas": "pandas", "numpy": "numpy",
    "flask": "flask", "django": "django",
}

HARD_SKILLS = {
    "python","java","javascript","typescript","cplusplus","csharp","go","ruby",
    "swift","kotlin","rust","scala","react","vue","angular","nextjs","node",
    "express","django","flask","fastapi","spring","mysql","postgres","mongodb",
    "sqlserver","redis","elasticsearch","aws","gcp","azure","kubernetes","docker",
    "terraform","ansible","cicd","jenkins","linux","bash","sql","nosql","rest",
    "graphql","api","microservices","machine learning","artificial intelligence",
    "natural language processing","tensorflow","pytorch","pandas","numpy","git",
    "html","css","webpack","figma","tableau","power bi","excel","salesforce",
    "sap","jira","confluence","r","matlab","spark","hadoop","kafka",
    "tailwindcss","tailwind","postman","intellij","owasp","django",
}
SOFT_SKILLS = {
    "communication","teamwork","leadership","problem solving","adaptability",
    "creativity","collaboration","time management","critical thinking",
    "detail oriented","self motivated","initiative","organization",
    "presentation","negotiation","mentoring","coaching","conflict resolution",
    "decision making","prioritization","flexibility","multitasking","research",
    "analytical","interpersonal","empathy","accountability","dependable",
    "reliable","innovative","proactive","attention to detail","troubleshooting",
}
CERTIFICATIONS = {
    "aws certified","azure certified","google certified","pmp","cissp",
    "comptia","ccna","ccnp","cpa","cfa","cisa","itil","six sigma",
    "scrum master","csm","capm","prince2","rhcsa","tensorflow developer",
}
TOOLS = {
    "git","jira","confluence","slack","trello","asana","notion","figma",
    "sketch","adobe","photoshop","vs code","intellij","eclipse","xcode",
    "postman","datadog","grafana","prometheus","jenkins","travis","circleci",
    "microsoft office","google workspace","zoom","teams","tailwindcss",
}

SECTION_PATTERNS = {
    "experience": r'\b(work\s+experience|experience|employment|professional\s+background|work\s+history)\b',
    "education":  r'\b(education|academic|degree|university|college|school)\b',
    "skills":     r'\b(skills?|technical\s+skills?|competencies|expertise|proficiencies)\b',
    "projects":   r'\b(projects?|portfolio|open\s+source)\b',
    "certifications": r'\b(certifications?|licenses?|credentials?)\b',
    "summary":    r'\b(summary|objective|profile|about\s+me|overview)\b',
}

RAW_PRESENCE_MAP = {
    "flask":         [r'\bflask\b'],
    "django":        [r'\bdjango\b'],
    "graphql":       [r'\bgraphql\b'],
    "aws":           [r'\baws\b', r'\bamazon web services\b'],
    "gcp":           [r'\bgcp\b', r'\bgoogle cloud\b'],
    "azure":         [r'\bazure\b', r'\bmicrosoft azure\b'],
    "kubernetes":    [r'\bkubernetes\b', r'\bk8s\b'],
    "docker":        [r'\bdocker\b'],
    "jenkins":       [r'\bjenkins\b'],
    "jira":          [r'\bjira\b'],
    "linux":         [r'\blinux\b'],
    "bash":          [r'\bbash\b'],
    "redis":         [r'\bredis\b'],
    "mongodb":       [r'\bmongodb\b', r'\bmongo\b'],
    "postgres":      [r'\bpostgres\b', r'\bpostgresql\b'],
    "react":         [r'\breact\b', r'\breactjs\b', r'\breact\.js\b'],
    "node":          [r'\bnode\b', r'\bnodejs\b', r'\bnode\.js\b', r'\bnord\.js\b'],
    "javascript":    [r'\bjavascript\b', r'\bjs\b'],
    "typescript":    [r'\btypescript\b'],
    "python":        [r'\bpython\b'],
    "java":          [r'\bjava\b'],
    "git":           [r'\bgit\b', r'\bgithub\b', r'\bgitlab\b'],
    "agile":         [r'\bagile\b', r'\bscrum\b', r'\bkanban\b'],
    "sql":           [r'\bsql\b'],
    "machine learning": [r'\bmachine learning\b', r'\bml\b'],
    "cicd":          [r'\bci/cd\b', r'\bcicd\b'],
    "rest":          [r'\brest\b', r'\brestful\b', r'\brest api\b'],
    "api":           [r'\bapi\b'],
    "microservices": [r'\bmicroservice'],
    "tensorflow":    [r'\btensorflow\b'],
    "pandas":        [r'\bpandas\b'],
    "numpy":         [r'\bnumpy\b'],
    "cplusplus":     [r'\bc\+\+\b', r'\bcpp\b'],
    "csharp":        [r'\bc#\b'],
    "tailwindcss":   [r'\btailwind\b', r'\btailwindcss\b'],
    "postman":       [r'\bpostman\b'],
    "owasp":         [r'\bowasp\b'],
    "nextjs":        [r'\bnext\.js\b', r'\bnextjs\b'],
}

# ── Measurable results patterns ──────────────────────────────────────
MEASURABLE_PATTERN = re.compile(
    r'\b(\d+[\+%xX]|\d+\s*(percent|%|times|x|users|customers|hours|days|weeks|months|million|thousand|k\b))',
    re.IGNORECASE
)

# ── Action verbs ──────────────────────────────────────────────────────
ACTION_VERBS = {
    "developed","built","created","designed","implemented","engineered",
    "deployed","led","managed","optimized","improved","increased","reduced",
    "automated","collaborated","delivered","maintained","resolved","enhanced",
    "architected","migrated","integrated","launched","established","streamlined",
}


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())


def apply_synonyms(token: str) -> str:
    return SYNONYMS.get(token, token)


def raw_contains(resume_text: str, keyword: str) -> bool:
    text_lower = resume_text.lower()
    patterns = RAW_PRESENCE_MAP.get(keyword, [])
    for pat in patterns:
        if re.search(pat, text_lower):
            return True
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text_lower))


def count_in_text(text: str, keyword: str) -> int:
    """Count how many times a keyword appears in text."""
    text_lower = text.lower()
    patterns = RAW_PRESENCE_MAP.get(keyword, [r'\b' + re.escape(keyword) + r'\b'])
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, text_lower))
    return min(count, 9)  # cap at 9 for display


def detect_sections(text: str) -> dict:
    sections = defaultdict(str)
    lines = text.split('\n')
    current_section = 'other'
    for line in lines:
        stripped = line.strip()
        matched = None
        for section, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, stripped, re.IGNORECASE) and len(stripped) < 60:
                matched = section
                break
        if matched:
            current_section = matched
        else:
            sections[current_section] += line + '\n'
    return dict(sections)


def extract_keywords(text: str, nlp) -> set:
    doc = nlp(normalize(text))
    keywords = set()
    for token in doc:
        if token.is_alpha and not token.is_stop and len(token.lemma_) > 2:
            keywords.add(apply_synonyms(token.lemma_))
    word_list = [t.text for t in doc if not t.is_punct and not t.is_space]
    for n in (2, 3):
        for i in range(len(word_list) - n + 1):
            phrase = " ".join(word_list[i:i+n])
            canonical = apply_synonyms(phrase)
            if (canonical != phrase
                    or phrase in SOFT_SKILLS
                    or phrase in CERTIFICATIONS
                    or phrase in HARD_SKILLS):
                keywords.add(canonical)
    return keywords


def compute_tfidf(text: str, corpus_texts: list, nlp) -> dict:
    doc = nlp(normalize(text))
    tokens = [apply_synonyms(t.lemma_) for t in doc
              if t.is_alpha and not t.is_stop and len(t.lemma_) > 2]
    if not tokens:
        return {}
    tf_counts = Counter(tokens)
    total_terms = len(tokens)
    tf = {term: count / total_terms for term, count in tf_counts.items()}
    N = len(corpus_texts) + 1
    df = defaultdict(int)
    for corpus_text in corpus_texts:
        corpus_doc = nlp(normalize(corpus_text))
        corpus_lemmas = set(apply_synonyms(t.lemma_) for t in corpus_doc
                            if t.is_alpha and not t.is_stop and len(t.lemma_) > 2)
        for lemma in corpus_lemmas:
            df[lemma] += 1
    idf = {term: math.log(N / (df.get(term, 0) + 1)) + 1 for term in tf}
    return {term: tf[term] * idf[term] for term in tf}


def categorize(kw: str) -> str:
    if kw in HARD_SKILLS:
        return "hard_skill"
    if kw in SOFT_SKILLS:
        return "soft_skill"
    if any(c in kw for c in CERTIFICATIONS):
        return "certification"
    if kw in TOOLS:
        return "tool"
    return "other"


def suggest_placement(kw: str, cat: str, resume_sections: dict) -> str:
    if cat == "hard_skill":
        return "Add to your Skills section" if "skills" in resume_sections else "Add a Skills section"
    if cat == "soft_skill":
        return "Weave into your Summary or Experience bullets"
    if cat == "tool":
        return "Add to your Skills / Tools section"
    if cat == "certification":
        return "Add to Certifications section"
    return "Add where most relevant"


# ── Searchability checks ────────────────────────────────────────────
def check_searchability(resume_text: str, sections: dict) -> list:
    checks = []
    text_lower = resume_text.lower()

    # Contact info
    has_email = bool(re.search(r'[\w.+-]+@[\w-]+\.\w+', resume_text))
    has_phone = bool(re.search(r'[\+\(]?[\d\s\-\(\)]{7,}', resume_text))
    has_linkedin = bool(re.search(r'linkedin\.com', text_lower))
    has_address = bool(re.search(r'\b(street|ave|blvd|road|city|state|[A-Z]{2}\s+\d{5}|cape girardeau|missouri|mo\b)', text_lower))

    checks.append({
        "label": "Email address",
        "status": "pass" if has_email else "fail",
        "detail": "Email found — recruiters can contact you." if has_email else "No email found. Add your email address.",
    })
    checks.append({
        "label": "Phone number",
        "status": "pass" if has_phone else "fail",
        "detail": "Phone number found." if has_phone else "No phone number found. Add your phone number.",
    })
    checks.append({
        "label": "Location / Address",
        "status": "pass" if has_address else "warn",
        "detail": "Location found." if has_address else "No location detected. Recruiters use this for job matches.",
    })
    checks.append({
        "label": "LinkedIn profile",
        "status": "pass" if has_linkedin else "warn",
        "detail": "LinkedIn URL found." if has_linkedin else "No LinkedIn URL. Consider adding it.",
    })

    # Section headings
    for sec in ["experience", "education", "skills"]:
        found = sec in sections and sections[sec].strip()
        checks.append({
            "label": f"{sec.title()} section",
            "status": "pass" if found else "fail",
            "detail": f"{sec.title()} section detected." if found else f"No {sec} section found. Add a clear '{sec.title()}' heading.",
        })

    has_summary = "summary" in sections and sections["summary"].strip()
    checks.append({
        "label": "Summary / Objective",
        "status": "warn" if not has_summary else "pass",
        "detail": "Summary found." if has_summary else "No summary section. A brief professional summary helps recruiters quickly grasp your value.",
    })

    # Date formatting
    has_dates = bool(re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b', text_lower))
    checks.append({
        "label": "Date formatting",
        "status": "pass" if has_dates else "warn",
        "detail": "Employment dates detected." if has_dates else "No dates found in experience. Add date ranges.",
    })

    # Education match
    has_edu = "education" in sections and sections["education"].strip()
    checks.append({
        "label": "Education section",
        "status": "pass" if has_edu else "fail",
        "detail": "Education section found." if has_edu else "No education section detected.",
    })

    return checks


# ── Recruiter tip checks ────────────────────────────────────────────
def check_recruiter_tips(resume_text: str, sections: dict) -> list:
    tips = []
    text_lower = resume_text.lower()

    # Measurable results
    measurable_matches = MEASURABLE_PATTERN.findall(resume_text)
    count_measurable = len(measurable_matches)
    tips.append({
        "label": "Measurable results",
        "status": "pass" if count_measurable >= 3 else "warn",
        "detail": f"{count_measurable} measurable result(s) found. Keep it up!" if count_measurable >= 3
                  else f"Only {count_measurable} measurable result(s). Add percentages, numbers, and impact metrics.",
    })

    # Action verbs
    words = set(text_lower.split())
    action_count = len(words & ACTION_VERBS)
    tips.append({
        "label": "Action verbs",
        "status": "pass" if action_count >= 4 else "warn",
        "detail": f"{action_count} strong action verb(s) found." if action_count >= 4
                  else f"Only {action_count} action verb(s). Start bullets with strong verbs like 'Developed', 'Led', 'Optimized'.",
    })

    # Buzzwords / clichés
    buzzwords = ["hardworking","team player","go-getter","think outside","synergy","passionate","guru","ninja","rockstar"]
    found_buzz = [b for b in buzzwords if b in text_lower]
    tips.append({
        "label": "Resume tone",
        "status": "warn" if found_buzz else "pass",
        "detail": f"Clichés found: {', '.join(found_buzz)}. Replace with specific achievements." if found_buzz
                  else "No clichés or buzzwords found. Good tone.",
    })

    # Web presence
    has_web = bool(re.search(r'(github\.com|linkedin\.com|portfolio|website|http)', text_lower))
    tips.append({
        "label": "Web presence",
        "status": "pass" if has_web else "warn",
        "detail": "Online profile or portfolio URL found." if has_web
                  else "No web presence detected. Add a GitHub or portfolio link.",
    })

    # Job level
    tips.append({
        "label": "Job level match",
        "status": "warn",
        "detail": "Compare your years of experience to the job requirements to ensure alignment.",
    })

    return tips


def analyze(resume_text: str, job_text: str, nlp) -> dict:
    resume_sections = detect_sections(resume_text)
    resume_kws = extract_keywords(resume_text, nlp)
    job_kws    = extract_keywords(job_text, nlp)
    job_tfidf  = compute_tfidf(job_text, [resume_text], nlp)

    matched = set()
    missing = set()
    for kw in job_kws:
        if kw in resume_kws or raw_contains(resume_text, kw):
            matched.add(kw)
        else:
            missing.add(kw)

    # Weighted TF-IDF score
    total_weight   = sum(job_tfidf.get(kw, 0.1) for kw in job_kws)
    matched_weight = sum(job_tfidf.get(kw, 0.1) for kw in matched)
    weighted_score = int((matched_weight / total_weight) * 100) if total_weight > 0 else 0
    simple_score   = int((len(matched) / len(job_kws)) * 100) if job_kws else 0
    score = max(0, min(100, int(0.7 * weighted_score + 0.3 * simple_score)))

    # Categorize
    matched_by_cat = defaultdict(list)
    missing_by_cat = defaultdict(list)
    for kw in sorted(matched):
        matched_by_cat[categorize(kw)].append(kw)
    for kw in sorted(missing):
        missing_by_cat[categorize(kw)].append(kw)

    def cat_score(cat):
        m = len(matched_by_cat[cat])
        t = m + len(missing_by_cat[cat])
        return int((m / t) * 100) if t else None

    sub_scores = {
        "hard_skills":    cat_score("hard_skill"),
        "soft_skills":    cat_score("soft_skill"),
        "tools":          cat_score("tool"),
        "certifications": cat_score("certification"),
    }

    # Skills comparison table (Jobscan-style)
    all_skills = sorted(job_kws, key=lambda k: job_tfidf.get(k, 0), reverse=True)
    skills_table = []
    for kw in all_skills[:40]:
        resume_count = count_in_text(resume_text, kw)
        job_count    = count_in_text(job_text, kw)
        in_resume    = kw in matched
        skills_table.append({
            "keyword":      kw,
            "category":     categorize(kw),
            "resume_count": resume_count,
            "job_count":    job_count,
            "in_resume":    in_resume,
            "tfidf":        round(job_tfidf.get(kw, 0), 4),
        })

    # Contextual suggestions
    suggestions = []
    for cat in ["hard_skill", "soft_skill", "tool", "certification", "other"]:
        gaps = missing_by_cat.get(cat, [])
        gaps_sorted = sorted(gaps, key=lambda k: job_tfidf.get(k, 0), reverse=True)
        for kw in gaps_sorted[:4]:
            suggestions.append({
                "keyword":   kw,
                "category":  cat,
                "tfidf":     round(job_tfidf.get(kw, 0), 4),
                "placement": suggest_placement(kw, cat, resume_sections),
            })

    # Searchability + recruiter checks
    searchability_checks = check_searchability(resume_text, resume_sections)
    recruiter_tips       = check_recruiter_tips(resume_text, resume_sections)

    searchability_issues = sum(1 for c in searchability_checks if c["status"] == "fail")
    searchability_warns  = sum(1 for c in searchability_checks if c["status"] == "warn")
    hard_skill_issues    = len(missing_by_cat.get("hard_skill", []))
    soft_skill_issues    = len(missing_by_cat.get("soft_skill", []))
    recruiter_issues     = sum(1 for t in recruiter_tips if t["status"] != "pass")

    sections_found = [s for s in resume_sections if s != 'other' and resume_sections[s].strip()]

    return {
        "score":              score,
        "weighted_score":     weighted_score,
        "simple_score":       simple_score,
        "matched":            sorted(matched),
        "missing":            sorted(missing),
        "matched_count":      len(matched),
        "missing_count":      len(missing),
        "total_job_keywords": len(job_kws),
        "resume_keyword_count": len(resume_kws),
        "matched_by_cat":     dict(matched_by_cat),
        "missing_by_cat":     dict(missing_by_cat),
        "sub_scores":         sub_scores,
        "suggestions":        suggestions,
        "skills_table":       skills_table,
        "searchability_checks":    searchability_checks,
        "recruiter_tips":          recruiter_tips,
        "searchability_issues":    searchability_issues,
        "searchability_warns":     searchability_warns,
        "hard_skill_issues":       hard_skill_issues,
        "soft_skill_issues":       soft_skill_issues,
        "recruiter_issues":        recruiter_issues,
        "sections_found":          sections_found,
        "resume_word_count":       len(resume_text.split()),
        "job_word_count":          len(job_text.split()),
        "top_missing":             sorted(missing, key=lambda k: job_tfidf.get(k, 0), reverse=True)[:10],
        "resume_text":             resume_text,
        "job_text":                job_text,
    }
