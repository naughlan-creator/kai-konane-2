from enum import Enum as PyEnum
from flask_login import UserMixin
from config import db

class Role(PyEnum):
    ADMIN = "ADMIN"
    CHILD = "CHILD"
    PARENT = "PARENT"
    TEACHER = "TEACHER"

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.Enum(Role, name='role'), nullable=False)
    type = db.Column(db.String(50))

    sent_feedbacks = db.relationship('Feedback', foreign_keys='Feedback.sender_id', back_populates='sender')
    received_feedbacks = db.relationship('Feedback', foreign_keys='Feedback.recipient_id', back_populates='recipient')
    
    __mapper_args__ = {
        "polymorphic_identity": "user",
        "polymorphic_on": type
    }

    def get_id(self):
        return str(self.id)
