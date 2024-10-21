from .user import User
from .child import EducationLevel
from config import db

class Parent(User):
    __tablename__ = 'parents'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    firstname = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    education_level = db.Column(db.Enum(EducationLevel, name='education_level'), nullable=False)

    children = db.relationship("Child", back_populates="parent", foreign_keys='Child.parent_id')

    __mapper_args__ = {
        'polymorphic_identity': 'parent',
    }
