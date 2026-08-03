from .user import User
from config import db

class Teacher(User):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    preschool_id = db.Column(db.Integer, db.ForeignKey('preschools.id', ondelete='SET NULL'),
                             index=True)

    # Losing a teacher must not delete their learners: the FK is SET NULL, so
    # the children stay and can be reassigned.
    students = db.relationship("Child", back_populates="teacher",
                               foreign_keys='Child.teacher_id')
    preschool = db.relationship("Preschool", back_populates="teachers")

    __mapper_args__ = {
        'polymorphic_identity': 'teacher',
    }
