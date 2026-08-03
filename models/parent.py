from .user import User
from .child import EducationLevel
from config import db

class Parent(User):
    __tablename__ = 'parents'

    id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    education_level = db.Column(db.Enum(EducationLevel, name='education_level'), nullable=False)

    children = db.relationship("Child", back_populates="parent",
                               foreign_keys='Child.parent_id',
                               cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': 'parent',
    }
