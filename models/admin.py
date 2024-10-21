from .user import User
from config import db

class Admin(User):
    __tablename__ = 'admin'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.String(5))

    __mapper_args__ = {
        'polymorphic_identity': 'admin',
    }