from enum import Enum as PyEnum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import db
from app.utils import utcnow


class Role(PyEnum):
    ADMIN = "ADMIN"
    CHILD = "CHILD"
    PARENT = "PARENT"
    TEACHER = "TEACHER"

    @classmethod
    def coerce(cls, value, default=None):
        if isinstance(value, cls):
            return value
        if value is None:
            return default
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            return default


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    role = db.Column(db.Enum(Role, name='role'), nullable=False, index=True)
    type = db.Column(db.String(50), index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    sent_feedbacks = db.relationship('Feedback', foreign_keys='Feedback.sender_id',
                                     back_populates='sender', cascade="all, delete-orphan")
    received_feedbacks = db.relationship('Feedback', foreign_keys='Feedback.recipient_id',
                                         back_populates='recipient', cascade="all, delete-orphan")

    __mapper_args__ = {
        "polymorphic_identity": "user",
        "polymorphic_on": type
    }

    def get_id(self):
        return str(self.id)

    def set_password(self, raw_password):
        """Hash and store a password. Keeps hashing in one place."""
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password or not raw_password:
            return False
        return check_password_hash(self.password, raw_password)

    @property
    def display_name(self):
        """A human name for templates, whatever the subclass."""
        first = getattr(self, 'firstname', None)
        last = getattr(self, 'lastname', None)
        if first or last:
            return ' '.join(part for part in (first, last) if part)
        return getattr(self, 'name', None) or self.username

    def __repr__(self):
        return f"<{type(self).__name__} {self.id} {self.username!r}>"
