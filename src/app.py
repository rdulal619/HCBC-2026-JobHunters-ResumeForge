import os
from datetime import datetime
from flask import (Flask, render_template, request, flash, redirect,
                   url_for, session, make_response, abort, jsonify)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from config import config
from models import db, bcrypt, User, Analysis
from services import parser
from services.analyzer import analyze
from services.checker import check_resume as run_checker
from services.report import generate_pdf_report

import spacy

# ── spaCy model ──────────────────────────────────────────────────────────
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    Session(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access your history.'
    login_manager.login_message_category = 'info'

    limiter = Limiter(get_remote_address, app=app,
                      default_limits=["200 per day", "60 per hour"],
                      storage_uri="memory://")

    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    @app.after_request
    def add_no_cache(response):
        # Prevent browser caching authenticated pages
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # ── Helpers ───────────────────────────────────────────────────────────
    def get_text_from_request(file_field, text_field):
        """Extract text from uploaded file or pasted textarea."""
        f = request.files.get(file_field)
        pasted = request.form.get(text_field, '').strip()
        if f and f.filename:
            if not parser.allowed_file(f.filename):
                return None, 'Invalid file type. Use PDF, DOCX, or TXT.'
            filename = secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
            try:
                text = parser.extract_text(filepath, filename)
                flash(f'"{filename}" processed — {len(text):,} characters extracted.', 'success')
                return text, None
            except Exception as e:
                return None, f'Could not read file: {e}'
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
        if pasted:
            return pasted, None
        return None, None

    def store_analysis(results, job_title=''):
        """Persist analysis to DB if user logged in, always store in session."""
        session['results'] = {
            'score':                results['score'],
            'matched':              results['matched'][:40],
            'missing':              results['missing'][:40],
            'matched_count':        results['matched_count'],
            'missing_count':        results['missing_count'],
            'total_job_keywords':   results['total_job_keywords'],
            'resume_keyword_count': results['resume_keyword_count'],
            'sub_scores':           results['sub_scores'],
            'matched_by_cat':       results['matched_by_cat'],
            'missing_by_cat':       results['missing_by_cat'],
            'suggestions':          results['suggestions'],
            'sections_found':       results['sections_found'],
            'resume_word_count':    results['resume_word_count'],
            'job_word_count':       results['job_word_count'],
            'top_missing':          results['top_missing'],
            'weighted_score':       results['weighted_score'],
            'simple_score':         results['simple_score'],
            'skills_table':         results.get('skills_table', [])[:25],
            'searchability_checks': results.get('searchability_checks', []),
            'recruiter_tips':        results.get('recruiter_tips', []),
            'searchability_issues':  results.get('searchability_issues', 0),
            'searchability_warns':   results.get('searchability_warns', 0),
            'hard_skill_issues':     results.get('hard_skill_issues', 0),
            'soft_skill_issues':     results.get('soft_skill_issues', 0),
            'recruiter_issues':      results.get('recruiter_issues', 0),
        }

        if current_user.is_authenticated:
            record = Analysis(
                user_id=current_user.id,
                job_title=job_title or 'Untitled',
                score=results['score'],
                matched_count=results['matched_count'],
                missing_count=results['missing_count'],
                total_keywords=results['total_job_keywords'],
                hard_skills_score=results['sub_scores'].get('hard_skills'),
                soft_skills_score=results['sub_scores'].get('soft_skills'),
                tools_score=results['sub_scores'].get('tools'),
                matched_keywords=','.join(results['matched'][:40]),
                missing_keywords=','.join(results['missing'][:40]),
            )
            db.session.add(record)
            db.session.commit()

    # ── Auth routes ───────────────────────────────────────────────────────
    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit("10 per hour")
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            name  = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip() or None
            pw    = request.form.get('password', '')
            pw2   = request.form.get('confirm_password', '')

            if not name or not email or not pw:
                flash('Name, email and password are required.', 'error')
                return render_template('register.html')
            if pw != pw2:
                flash('Passwords do not match.', 'error')
                return render_template('register.html')
            if len(pw) < 8:
                flash('Password must be at least 8 characters.', 'error')
                return render_template('register.html')
            if User.query.filter_by(email=email).first():
                flash('An account with this email already exists.', 'error')
                return render_template('register.html')
            if phone and User.query.filter_by(phone=phone).first():
                flash('An account with this phone number already exists.', 'error')
                return render_template('register.html')

            user = User(name=name, email=email, phone=phone, is_verified=True)
            user.set_password(pw)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash(f'Welcome to ResumeForge, {name}! Your account has been created.', 'success')
            return redirect(url_for('dashboard'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit("20 per hour")
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            identifier = request.form.get('identifier', '').strip()
            password   = request.form.get('password', '')
            remember   = request.form.get('remember') == 'on'

            # Support login by email or phone
            user = User.query.filter(
                (User.email == identifier.lower()) |
                (User.phone == identifier)
            ).first()

            if user and user.check_password(password):
                user.last_login = datetime.utcnow()
                db.session.commit()
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                flash(f'Welcome back, {user.name}!', 'success')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid email/phone or password.', 'error')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        logout_user()
        session.clear()
        # Delete the session cookie completely
        response = make_response(redirect(url_for('landing')))
        response.delete_cookie('session')
        response.delete_cookie('remember_token')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        flash('You have been logged out successfully.', 'success')
        return response

    # ── Core routes ───────────────────────────────────────────────────────
    @app.route('/')
    def landing():
        return render_template('landing.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        analyses = (Analysis.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Analysis.created_at.desc())
                    .limit(10).all())
        avg_score = None
        if analyses:
            avg_score = int(sum(a.score for a in analyses) / len(analyses))
        return render_template('dashboard.html', analyses=analyses, avg_score=avg_score)

    @app.route('/analyze-page')
    def analyze_page():
        return render_template('index.html')

    @app.route('/analyze', methods=['POST'])
    @limiter.limit("30 per hour")
    def analyze_route():
        # Clear previous resume results so the new job/resume flow starts clean
        for key in ['resume_text_raw','resume_text_original','job_text_raw','results','checker_report','rewritten_resume']:
            session.pop(key, None)

        resume_text, r_err = get_text_from_request('resume_file', 'resume_text')
        job_text,    j_err = get_text_from_request('job_file',    'job_text')
        job_title = request.form.get('job_title', '').strip()

        for err in [r_err, j_err]:
            if err:
                flash(err, 'error')
                return redirect(url_for('analyze_page'))

        if not resume_text:
            flash('Please provide your resume (upload or paste).', 'error')
            return redirect(url_for('analyze_page'))
        if not job_text:
            flash('Please provide the job description (upload or paste).', 'error')
            return redirect(url_for('analyze_page'))

        results = analyze(resume_text, job_text, nlp)
        store_analysis(results, job_title)
        session['resume_text_raw'] = resume_text[:8000]
        session['resume_text_original'] = resume_text[:8000]  # never overwritten
        session['job_text_raw'] = job_text[:8000]
        session.modified = True
        return redirect(url_for('results'))

    @app.route('/results')
    def results():
        r = session.get('results')
        if not r:
            flash('No results yet. Please run an analysis first.', 'error')
            return redirect(url_for('analyze_page'))
        # Inject defaults for any missing keys (backward compat with old sessions)
        defaults = {
            'skills_table': [],
            'searchability_checks': [],
            'recruiter_tips': [],
            'searchability_issues': 0,
            'searchability_warns': 0,
            'hard_skill_issues': len(r.get('missing_by_cat', {}).get('hard_skill', [])),
            'soft_skill_issues': len(r.get('missing_by_cat', {}).get('soft_skill', [])),
            'recruiter_issues': 0,
            'matched_by_cat': {},
            'missing_by_cat': {},
            'suggestions': [],
            'sections_found': [],
            'top_missing': [],
            'sub_scores': {},
            'weighted_score': r.get('score', 0),
            'simple_score': r.get('score', 0),
        }
        for k, v in defaults.items():
            if k not in r:
                r[k] = v
        return render_template('results.html', r=r)

    @app.route('/report.pdf')
    def download_report():
        r = session.get('results')
        if not r:
            flash('No results to export.', 'error')
            return redirect(url_for('analyze_page'))
        name = current_user.name if current_user.is_authenticated else 'Guest'
        pdf_bytes = generate_pdf_report(r, user_name=name)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=ResumeForge_Report.pdf'
        return response

    @app.route('/history')
    @login_required
    def history():
        analyses = (Analysis.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Analysis.created_at.desc())
                    .all())
        return render_template('history.html', analyses=analyses)

    @app.route('/history/delete/<int:analysis_id>', methods=['POST'])
    @login_required
    def delete_analysis(analysis_id):
        a = Analysis.query.get_or_404(analysis_id)
        if a.user_id != current_user.id:
            abort(403)
        db.session.delete(a)
        db.session.commit()
        flash('Analysis deleted.', 'success')
        return redirect(url_for('history'))

    @app.route('/clear')
    def clear_session():
        session.clear()
        flash('Session data cleared.', 'success')
        return redirect(url_for('landing'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        if request.method == 'POST':
            name  = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip() or None
            if name:
                current_user.name = name
            current_user.phone = phone
            db.session.commit()
            flash('Profile updated.', 'success')
        return render_template('profile.html')

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404,
                               message="Page not found"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403,
                               message="Access denied"), 403

    @app.errorhandler(429)
    def too_many(e):
        return render_template('error.html', code=429,
                               message="Too many requests. Please slow down."), 429

    @app.route('/check', methods=['POST'])
    @limiter.limit("30 per hour")
    def check_resume_route():
        """Enhancv-style: upload resume → get quality score, no job description needed."""
        # Clear only resume-specific keys to avoid accidentally logging out authenticated users
        for key in ['resume_text_raw','resume_text_original','job_text_raw','results','checker_report','rewritten_resume']:
            session.pop(key, None)

        resume_text, r_err = get_text_from_request('resume_file', 'resume_text')
        if r_err:
            flash(r_err, 'error')
            return redirect(url_for('analyze_page'))
        if not resume_text:
            flash('Please upload a resume file or paste your resume text.', 'error')
            return redirect(url_for('analyze_page'))

        report = run_checker(resume_text)
        # Clean garbled characters from PDF icon fonts
        import re
        resume_text = re.sub(r'\(cid:\d+\)', '', resume_text)
        resume_text = re.sub(r'\s+', ' ', resume_text).strip()
        session['checker_report'] = report
        session['resume_text_raw'] = resume_text[:8000]
        session['resume_text_original'] = resume_text[:8000]  # never overwritten
        session.modified = True
        return render_template('checker_results.html', report=report,
                               resume_text=resume_text[:6000])

    @app.route('/tailor', methods=['POST'])
    @limiter.limit("20 per hour")
    def tailor_resume():
        """Takes resume from session + job description from form → full analysis."""
        resume_text = session.get('resume_text_raw', '')
        job_text    = request.form.get('job_text', '').strip()
        job_title   = request.form.get('job_title', '').strip()

        if not resume_text:
            flash('Session expired. Please re-upload your resume.', 'error')
            return redirect(url_for('analyze_page'))
        if not job_text:
            flash('Please paste a job description before tailoring.', 'error')
            return redirect(request.referrer or url_for('analyze_page'))

        results = analyze(resume_text, job_text, nlp)
        store_analysis(results, job_title)
        # Only set job text — resume_text_raw already set from original upload
        if not session.get('resume_text_raw'):
            session['resume_text_raw'] = resume_text
        session['resume_text_original'] = session.get('resume_text_original') or resume_text
        session['job_text_raw'] = job_text
        session.modified = True
        return redirect(url_for('results'))

    @app.route('/upgrade')
    def upgrade():
        # Always show the original resume in the editor, not a previous rewrite
        resume_text = session.get('resume_text_original') or session.get('resume_text_raw', '')
        if not resume_text:
            flash('Please upload your resume first.', 'error')
            return redirect(url_for('analyze_page'))
        # Works from both checker flow and jobscan flow
        r = session.get('results') or {}
        checker = session.get('checker_report') or {}
        # Build a minimal r for the upgrade template
        if not r and checker:
            r = {
                'score': checker.get('overall', 0),
                'missing_by_cat': {'hard_skill': [], 'soft_skill': [], 'tool': []},
                'top_missing': [],
                'suggestions': [],
            }
        return render_template('upgrade.html', r=r, resume_text=resume_text)

    @app.route('/rewrite', methods=['POST'])
    @limiter.limit("10 per hour")
    def rewrite():
        """AI rewrite endpoint — uses Anthropic API (fast, reliable)."""
        resume_text = session.get('resume_text_original') or session.get('resume_text_raw', '')
        job_text    = session.get('job_text_raw', '')
        r           = session.get('results') or {}
        checker     = session.get('checker_report') or {}

        if not resume_text:
            return jsonify({'error': 'Session expired. Please re-upload your resume.'}), 400

        missing_hard = r.get('missing_by_cat', {}).get('hard_skill', [])
        missing_soft = r.get('missing_by_cat', {}).get('soft_skill', [])
        missing_tool = r.get('missing_by_cat', {}).get('tool', [])
        old_score    = r.get('score') or checker.get('overall', 0)
        keywords_to_add = (missing_hard[:8] + missing_tool[:4] + missing_soft[:4])[:12]

        pythonprompt = f"""You are an expert resume writer. Transform the resume below into a perfectly structured, ATS-optimized resume using this exact format.

═══ REQUIRED OUTPUT FORMAT ═══

[FULL NAME]
[Phone] | [Email] | [LinkedIn URL] | [City, State]

SUMMARY
[2-3 sentences. Professional third person but NEVER repeat the person's name. 
Example: "Senior AI Engineer with 3+ years building LLM pipelines and RAG systems..."]

TECHNICAL SKILLS
- Languages: [list]
- Frameworks & Libraries: [list]  
- Tools & Platforms: [list]
- Databases: [list]
- Other relevant categories as needed

EXPERIENCE

[Job Title] | [Company] | [Month Year – Month Year]
- [Strong action verb] + [specific task] + [quantified result]
- [Strong action verb] + [specific task] + [quantified result]
- [Strong action verb] + [specific task] + [quantified result]

[Repeat for each job]

PROJECTS

[Project Name] | [Tech Stack]
- [bullet specific to THIS project only]
- [bullet specific to THIS project only]

[Next Project Name] | [Tech Stack]  
- [bullet specific to THIS project only]

EDUCATION

[Degree] | [University] | [Year]
GPA: [X.X/4.0]
Relevant Coursework: [only if impressive]

ACHIEVEMENTS & LEADERSHIP
- [Award, scholarship, leadership role with context]

═══ TRANSFORMATION RULES ═══
1. PRESERVE everything — every job, every project, every achievement, every section
2. NEVER use first person — no I, my, myself, I am, I have
3. Every bullet MUST start with a strong past-tense action verb: Engineered, Built, Developed, Led, Automated, Optimized, Designed, Deployed, Reduced, Improved, Increased, Delivered, Architected, Launched, Implemented, Streamlined
4. Add metrics to EVERY bullet where possible — use estimates if needed (e.g. "15+ students weekly", "50+ applications processed daily", "reduced time by ~30%")
5. Keep ALL original company names, job titles, university names, and dates EXACTLY as they appear
6. Remove ALL weak phrases: "responsible for", "worked on", "helped", "assisted with", "was involved in", "participated in", "contributed to"
7. Skills section MUST come before Experience
8. Fix typos and grammar silently
9. If a section has no content in the original, completely omit it — never write "No X listed". Never invent content for empty sections
{f"10. Naturally include these missing keywords where truthful: {', '.join(keywords_to_add)}" if keywords_to_add else ""}

{f'TARGET JOB:{chr(10)}{job_text[:1500]}' if job_text else 'No job description — maximize overall quality.'}

═══ RESUME TO TRANSFORM ═══
{resume_text}

OUTPUT ONLY THE COMPLETE TRANSFORMED RESUME. Start with the person's full name. Include every single section from the original. Zero commentary. Zero notes."""

        try:
            import os
            groq_key = os.environ.get('GROQ_API_KEY', '')

            if groq_key:
                from groq import Groq
                client = Groq(api_key=groq_key)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": pythonprompt}],
                    max_tokens=2000,
                    temperature=0.3,
                )
                rewritten = response.choices[0].message.content.strip()
            else:
                # Fallback to Ollama only if no API key
                try:
                    import ollama
                    response = ollama.chat(
                        model='llama3.2',
                        messages=[{'role': 'user', 'content': pythonprompt}],
                        options={'temperature': 0.3, 'num_predict': 2000}
                    )
                    rewritten = response['message']['content'].strip()
                except Exception as ollama_err:
                    return jsonify({'error': f'No API key set and Ollama not running: {str(ollama_err)[:80]}'}), 500

            # Strip any commentary Llama/Claude appends
            import re as _re
            rewritten = _re.split(
                r'\n\s*(?:changes made|note:|notes:|changes:|summary of changes|what i changed)',
                rewritten, flags=_re.IGNORECASE
            )[0].strip()

            # Convert dashes to bullets for consistency
            rewritten = _re.sub(r'(?m)^(\s*)- ', r'\1• ', rewritten)

            # Save rewritten resume
            # Force session to save by reassigning
            rewritten_resume = rewritten
            session['rewritten_resume'] = rewritten_resume
            session['rewritten_resume_backup'] = rewritten_resume[:500]  # force dirty flag
            session.modified = True

            # Re-score: use checker if no job description, analyzer if job description exists
            if job_text:
                new_results = analyze(rewritten, job_text, nlp)
                new_score = new_results['score']
                updated = {k: v for k, v in new_results.items() if k not in ('resume_text', 'job_text')}
                updated['skills_table']         = updated.get('skills_table', [])[:25]
                updated['searchability_checks'] = updated.get('searchability_checks', [])
                updated['recruiter_tips']       = updated.get('recruiter_tips', [])
                updated['searchability_issues'] = updated.get('searchability_issues', 0)
                updated['searchability_warns']  = updated.get('searchability_warns', 0)
                updated['hard_skill_issues']    = updated.get('hard_skill_issues', 0)
                updated['soft_skill_issues']    = updated.get('soft_skill_issues', 0)
                updated['recruiter_issues']     = updated.get('recruiter_issues', 0)
                session['results'] = updated
            else:
                # No job description — re-run quality checker
                new_report = run_checker(rewritten)
                new_score = new_report['overall']
                # Never show a lower score after rewrite — take the better one
                if new_score < old_score:
                    new_score = old_score
                session['checker_report'] = new_report

            return jsonify({
                'rewritten':   rewritten,
                'old_score':   old_score,
                'new_score':   new_score,
                'improvement': new_score - old_score,
            })

        except Exception as e:
            return jsonify({'error': f'AI rewrite failed: {str(e)}'}), 500

    @app.route('/reanalyze', methods=['POST'])
    def reanalyze():
        """Re-analyze manually edited resume text."""
        data = request.get_json()
        edited_text = data.get('resume_text', '').strip()
        job_text    = session.get('job_text_raw', '')
        r           = session.get('results') or {}
        checker     = session.get('checker_report') or {}

        if not edited_text:
            return jsonify({'error': 'No resume text provided'}), 400

        # If no job description, just re-run the checker
        if not job_text:
            from services.checker import check_resume as run_checker
            new_report = run_checker(edited_text)
            old_score = checker.get('overall', 0)
            new_score = new_report['overall']
            session['checker_report'] = new_report
            session['rewritten_resume'] = edited_text
            # Keep resume_text_raw as original
            return jsonify({'old_score': old_score, 'new_score': new_score,
                            'improvement': new_score - old_score})

        old_score = r.get('score', 0) if r else 0
        new_results = analyze(edited_text, job_text, nlp)
        new_score = new_results['score']

        session['rewritten_resume'] = edited_text
        # Keep resume_text_raw as original
        updated = {k: v for k, v in new_results.items() if k not in ('resume_text','job_text')}
        updated['skills_table']         = updated.get('skills_table', [])[:25]
        updated['searchability_checks'] = updated.get('searchability_checks', [])
        updated['recruiter_tips']       = updated.get('recruiter_tips', [])
        updated['searchability_issues'] = updated.get('searchability_issues', 0)
        updated['searchability_warns']  = updated.get('searchability_warns', 0)
        updated['hard_skill_issues']    = updated.get('hard_skill_issues', 0)
        updated['soft_skill_issues']    = updated.get('soft_skill_issues', 0)
        updated['recruiter_issues']     = updated.get('recruiter_issues', 0)
        session['results'] = updated
        session['job_text_raw'] = job_text

        return jsonify({'old_score': old_score, 'new_score': new_score,
                        'improvement': new_score - old_score})

    @app.route('/download-resume')
    def download_resume():
        """Show template picker page."""
        resume_text = session.get('rewritten_resume') or session.get('resume_text_raw', '')
        if not resume_text:
            flash('No resume to download. Please run a rewrite first.', 'error')
            return redirect(url_for('upgrade'))
        return render_template('template_picker.html', resume_text=resume_text)

    @app.route('/download-resume/pdf')
    def download_resume_pdf():
        from services.resume_pdf import generate_resume_pdf, TEMPLATES
        resume_text = session.get('rewritten_resume', '').strip()
        if not resume_text:
            flash('Please run the AI rewrite first before downloading.', 'error')
            return redirect(url_for('upgrade'))
        template = request.args.get('template', 'classic')
        if template not in TEMPLATES:
            template = 'classic'
        pdf_bytes = generate_resume_pdf(resume_text, template)
        template_name = template.capitalize()
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Resume_{template_name}.pdf'
        return response

    return app


app = create_app(os.environ.get('FLASK_ENV', 'default'))

if __name__ == '__main__':
    app.run(debug=True)
