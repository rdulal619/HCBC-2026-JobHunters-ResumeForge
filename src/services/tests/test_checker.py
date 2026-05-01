import re
from services import checker


def test_bullets_and_numbered_lists():
    # Tests that BULLET_RE correctly detects dash-prefixed bullet points
    text = "- Did something important\n- Led the migration\n- Improved performance"
    bullets = checker._bullets(text)
    assert len(bullets) >= 3


def test_action_verbs_detection():
    # Tests that check_action_verbs() identifies strong verbs at start of bullets
    text = "- Developed the main API endpoints for the backend\n- Designed the database schema carefully\n- Maintained the documentation and tests"
    r = checker.check_action_verbs(text)
    assert r['total'] == 3
    assert r['strong'] >= 2


def test_spelling_grammar_flags_weak_phrases():
    # Tests that check_spelling_grammar() flags weak phrases like 'responsible for'
    text = "- Was responsible for deployment and monitoring\n- Helped with onboarding new team members"
    r = checker.check_spelling_grammar(text)
    assert r['count'] >= 1
    assert any('responsible for' in i.lower() for i in r['issues'])


def test_quantify_impact_flags_missing_numbers():
    # Tests that check_quantify_impact() flags bullets without measurable metrics
    text = "- Improved user experience by redesigning the onboarding flow which led to better retention\n- Reduced errors in the system"
    r = checker.check_quantify_impact(text)
    assert r['count'] >= 1