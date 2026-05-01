from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    analyses = db.relationship('Analysis', backref='user', lazy=True,
                               cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    job_title = db.Column(db.String(200), nullable=True)
    score = db.Column(db.Integer, nullable=False)
    matched_count = db.Column(db.Integer, default=0)
    missing_count = db.Column(db.Integer, default=0)
    total_keywords = db.Column(db.Integer, default=0)
    hard_skills_score = db.Column(db.Integer, nullable=True)
    soft_skills_score = db.Column(db.Integer, nullable=True)
    tools_score = db.Column(db.Integer, nullable=True)
    matched_keywords = db.Column(db.Text, nullable=True)   # comma-separated
    missing_keywords = db.Column(db.Text, nullable=True)   # comma-separated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def matched_list(self):
        return self.matched_keywords.split(',') if self.matched_keywords else []

    def missing_list(self):
        return self.missing_keywords.split(',') if self.missing_keywords else []

    def score_color(self):
        if self.score >= 70:
            return 'success'
        elif self.score >= 40:
            return 'warning'
        return 'danger'
