#!/usr/bin/env python3
"""
ResumeForge — Quick Setup Script (also supports pip install -e . via setuptools metadata)
"""
from setuptools import setup, find_packages
import subprocess
import sys
import os

# Make this project installable in CI and local editable installs
if any(cmd in sys.argv for cmd in ["install", "develop", "sdist", "bdist_wheel", "egg_info", "check"]):
    setup(
        name="resumeforge",
        version="0.1.0",
        packages=find_packages(include=["services", "services.*"]),
        include_package_data=True,
    )
    sys.exit(0)

def run(cmd, desc):
    print(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return False
    return True

print("\n=== ResumeForge Setup ===\n")

# 1. Install dependencies
run("pip install -r requirements.txt", "Installing Python packages")

# 2. Download spaCy model
run("python -m spacy download en_core_web_sm", "Downloading spaCy en_core_web_sm model")

# 3. Create .env if not exists
if not os.path.exists('.env'):
    import secrets
    key = secrets.token_hex(32)
    with open('.env', 'w') as f:
        f.write(f"SECRET_KEY={key}\n")
        f.write("FLASK_ENV=development\n")
        f.write("DATABASE_URL=sqlite:///resumeforge.db\n")
    print("  Created .env with a random SECRET_KEY")
else:
    print("  .env already exists — skipping")

# 4. Init DB
print("  Initializing database...")
try:
    from app import app
    from models import db
    with app.app_context():
        db.create_all()
    print("  Database tables created")
except Exception as e:
    print(f"  DB init error: {e}")

print("\n=== Setup complete ===")
print("\nTo run locally:")
print("  python app.py")
print("\nThen open: http://127.0.0.1:5000\n")
