from app.config import db

from .user import User


class Admin(User):
    __tablename__ = 'admin'

    id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    name = db.Column(db.String(100))

    __mapper_args__ = {
        'polymorphic_identity': 'admin',
    }
