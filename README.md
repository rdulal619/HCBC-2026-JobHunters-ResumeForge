# ResumeForge v2 — AI-Powered Resume Optimizer & Analyzer

[![CI / Tests & Lint](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/your-org/resumeforge/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask 3.0+](https://img.shields.io/badge/flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

**ResumeForge** is a production-ready Flask web application that helps users optimize and tailor their resumes using AI, job description analysis, and heuristic quality checks.


---

## Features

### 📋 Resume Quality Checker (Enhancv-Style)
- **ATS Parseability** — Detects formatting issues that applicant tracking systems struggle with
- **Content Quality** — Analyzes action verbs, quantified achievements, passive voice, buzzwords
- **Contact Info Validation** — Checks email professionalism, phone presence, LinkedIn/GitHub links
- **Multi-Dimensional Scoring** — Rates resume on content (40%), sections (30%), ATS essentials (20%), style (10%)

### 🎯 Job Tailoring & Keyword Matching
- **Keyword Extraction** — Identifies hard skills, soft skills, tools, and certifications from job description
- **Match Analysis** — Compares resume content to job requirements; flags missing keywords
- **Searchability Audits** — Spots recruiter pain points (inconsistent dates, weak formatting)
- **Weighted Scoring** — Produces overall match score with category breakdowns

### 🤖 AI-Powered Resume Rewriting
- **Ollama Integration** (free, local, no API key) — Uses `llama3.2` by default
- **Claude Fallback** — Uses Claude Haiku if `ANTHROPIC_API_KEY` is set
- **Smart Rewriting** — Maintains facts, adds metrics, uses action verbs, naturally incorporates keywords
- **Original Preservation** — Keeps original resume intact; never overwrites user input

### 👥 User Accounts & Analysis History
- Register/login with email or phone
- Persistent analysis history with scores and keyword metadata
- Dashboard with trends and average scores

### 📥 Multi-Format Resume Upload
- Accepts **PDF**, **DOCX**, **TXT** files
- Paste-as-text alternative
- Rate limiting to prevent abuse

### 📄 Flexible Exports
- Download analysis reports as **PDF**
- Export optimized resume in **multiple templates** (Classic, Modern, Minimal)

---

## Quick Start (Local Development)

### 1. Clone & Create Virtual Environment

```bash
git clone https://github.com/your-org/resumeforge.git
cd resumeforge
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize App

```bash
python setup.py
```

This will:
- Create `.env` with a random `SECRET_KEY`
- Initialize SQLite database at `instance/resumeforge.db`
- Create upload and instance folders

### 4. Run Dev Server

```bash
python app.py
```

Visit **http://127.0.0.1:5000** in your browser.

---

## Production Deployment

### Docker (Recommended for Any Cloud)

```bash
# Build image
docker build -t resumeforge:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -e FLASK_ENV=production \
  -v /data/resumeforge:/app/instance \
  resumeforge:latest
```

### Heroku, Render, Railway, AWS

All support the `Procfile` included in the repo:

```bash
git push heroku main  # Heroku example
```

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SECRET_KEY` | ✓ | Flask session signing key (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `FLASK_ENV` | ✓ | `production` for production, `development` for local |
| `DATABASE_URL` | ✗ | Override SQLite; e.g. `postgresql://user:pass@host/db` |
| `ANTHROPIC_API_KEY` | ✗ | Enables Claude-based rewrites; optional (uses Ollama by default) |
| `UPLOAD_FOLDER` | ✗ | Path to store resume uploads (default: `uploads/`) |

---

## Development Guide

### Install Dev & Test Dependencies

```bash
pip install -r requirements-dev.txt
```

Includes: **pytest**, **flake8**, **black**, optional **spacy** for NLP testing.

### Run Tests

```bash
pytest -v
```

All tests in `services/tests/` are automatically discovered and run.

### Lint & Format

```bash
flake8 app.py config.py models.py services/ --max-line-length=120
black app.py config.py models.py services/ --line-length=120
```

### Project Structure

```
resumeforge/
├── app.py                     # Flask app factory & all routes (500+ lines)
├── config.py                  # Environment configs (dev, test, prod)
├── models.py                  # SQLAlchemy: User, Analysis ORM models
├── setup.py                   # Initialize app (deps, DB, .env)
│
├── services/
│   ├── analyzer.py            # Core: TF-IDF, keyword matching, job tailoring
│   ├── checker.py             # Resume quality checks (14 dimensions)
│   ├── parser.py              # File parsing (PDF, DOCX, TXT)
│   ├── report.py              # PDF report generation (ReportLab)
│   ├── resume_pdf.py          # Resume template rendering
│   └── tests/
│       └── test_checker.py    # Unit tests for checker
│
├── templates/                 # Jinja2 HTML (13 templates)
│   ├── base.html              # Base layout
│   ├── landing.html           # Homepage
│   ├── index.html             # Analyzer form
│   ├── results.html           # Job match results
│   ├── checker_results.html   # Quality check results
│   ├── upgrade.html           # Rewrite editor
│   ├── template_picker.html   # Resume template selector
│   ├── login.html, register.html
│   ├── dashboard.html, history.html, profile.html
│   └── error.html
│
├── static/
│   ├── css/                   # Stylesheets
│   └── js/                    # Client-side scripts
│
├── uploads/                   # Temp storage for user uploads (auto-cleaned)
├── instance/                  # Instance data (DB, temp files)
│
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Dev & test dependencies
├── Dockerfile                 # Multi-stage Docker build
├── Procfile                   # Heroku/Railway deployment config
├── .github/workflows/
│   └── ci.yml                 # GitHub Actions: test + lint + Docker build
│
└── README.md (this file)
```

---

## Algorithm & Architecture

### Resume Quality Checking (Enhancv-Inspired)

`services/checker.py` runs **14 independent checks** on a resume and produces a final score:

**Content Quality** (40% weight):
- ATS parse rate — basic structure sanity check
- Quantify impact — flags bullets without metrics
- Repetition — detects overused words
- Spelling/grammar — heuristics for weak verbs, passive voice, buzzwords
- Action verbs — checks if bullets start with strong action verbs

**Sections** (30% weight):
- Essential sections — confirms Experience, Education, Skills present
- Contact info — validates email, phone, LinkedIn/GitHub
- Professional summary — checks for presence and substance

**ATS Essentials** (20% weight):
- Length — ensures 200–1200 words (1–2 pages)
- Dates — verifies employment date ranges
- File type — accepts PDF/DOCX/TXT
- Active voice — penalizes passive constructions

**Style** (10% weight):
- Bullet conciseness — flags bullets >30 words
- Email professionalism — detects suspicious email patterns

Each check returns: `status` (pass/warn/fail), `score` (0–100), and `detail` (human-readable feedback).

**Final Score** = 0.4 × content_score + 0.3 × sections_score + 0.2 × ats_score + 0.1 × style_score

### Job Tailoring & Keyword Matching

`services/analyzer.py` extracts keywords from a job description and compares to the resume:

1. **Tokenization** — spaCy (if available) or regex splits into words
2. **Lemmatization** — "developing", "developer", "develops" → "develop"
3. **Keyword Extraction** — Identifies hard skills (Python, SQL), soft skills (leadership, communication), tools (Git, Docker), certifications
4. **Resume Scanning** — Searches resume for each keyword (case-insensitive, lemma-aware)
5. **Categorization** — Tags missing keywords by type (hard_skill, soft_skill, tool, certification)
6. **Scoring** — match_count / total_keywords × 100 = overall match %
7. **Feedback** — Provides "top 5 missing keywords" and "section-by-section" breakdown

### AI Rewriting (Ollama + Claude)

When user requests a rewrite:

1. **Extraction** — Pulls original resume, job description, and missing keywords from session
2. **Prompt Engineering** — Constructs a detailed prompt ensuring:
   - Third-person language (no "I", "my")
   - All bullets start with strong action verbs
   - Metrics added where implied (e.g., "students" → "15+ students")
   - Keywords naturally incorporated
   - Original facts preserved
3. **API Call**:
   - First tries **Ollama** (localhost:11434) with `llama3.2` → free, no key, fast
   - Falls back to **Claude Haiku** if `ANTHROPIC_API_KEY` env var is set
4. **Re-Analysis** — Immediately re-analyzes rewritten resume and shows score delta
5. **Preview** — User can edit rewritten text, then re-analyze on-demand

---

## Accuracy & Limitations

### What's Accurate ✓
- Resume parsing (most PDFs, DOCXs, TXT files)
- Contact information detection (email, phone, URLs)
- Section detection (Experience, Education, Skills headers)
- Action verb analysis (checks if bullets start with strong verbs)
- ATS essentials (length, dates, formatting basics)
- Keyword matching (pattern + optional lemmatization)

### What You Should Know ⚠
- Grammar checks use heuristics + optional spaCy NLP (not 100% accurate)
- Passive voice detection falls back to regex if spaCy unavailable
- Complex/non-standard formatting (tables, multi-columns) may be skipped
- Docx parsing may not preserve all nuances (colors, fonts)

### Best Practices for Users
1. **Cross-test** with ATS simulators (TalenDesk, JobScan, Indeed)
2. **Manually review** AI rewrites — they're suggestions, not gospel
3. **A/B test** when possible — measure which resume version gets more callbacks
4. **Feedback loop** — report accuracy issues to improve heuristics

---

## Security & Best Practices

### Input Validation
- File uploads: Whitelist extensions, validate MIME type, enforce 10MB cap
- Text input: Strip whitespace, enforce length limits, use `.encode()` for safety
- Form input: No code injection via Jinja2 auto-escape and SQLAlchemy ORM

### Rate Limiting
- `10 per hour` — AI rewrite (expensive, prevents LLM abuse)
- `20 per hour` — Login, tailor (moderate complexity)
- `30 per hour` — Upload analyze, check (basic operations)

### Session & Authentication
- Signed cookies (itsdangerous via Flask)
- CSRF tokens on all HTML forms
- Cache headers prevent authenticated page caching
- Password hashing with bcrypt (not plaintext)

### Database
- SQLAlchemy ORM (prevents SQL injection)
- SQLite locally; upgrade to PostgreSQL for production
- `.env` stores secrets (not in code)

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'flask_login'`
```bash
pip install -r requirements.txt
```

### spaCy Model Issues (Python 3.13)
spaCy is optional and moved to `requirements-dev.txt`. The app gracefully falls back to regex heuristics without it.

### `ollamaAPIStatusError` on AI Rewrite
```bash
# Install & run Ollama locally
ollama serve
# Then try rewrite again
# OR set ANTHROPIC_API_KEY for Claude
```

### Resume Upload Fails
- Check file size (<10 MB)
- Confirm format: PDF, DOCX, or TXT only
- Ensure `uploads/` folder has write permissions
- Check browser console for client-side errors

### Tests Fail on CI
```bash
pytest -v --tb=short
# Common issues: DB locks, missing models, broken imports
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and test: `pytest -v`
4. Commit with clear messages: `git commit -m "Add feature"`
5. Push to your fork: `git push origin feature/my-feature`
6. Open a pull request with a clear description

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support & Contact

- **GitHub Issues** — Bug reports, feature requests
- **Email** — support@resumeforge.dev
- **Documentation** — https://docs.resumeforge.dev (coming soon)

---
