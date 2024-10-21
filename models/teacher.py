from .user import User
from config import db

class Teacher(User):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    firstname = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    preschool_id = db.Column(db.Integer, db.ForeignKey('preschools.id'))

    students = db.relationship("Child", back_populates="teacher", foreign_keys='Child.teacher_id')
    preschool = db.relationship("Preschool", back_populates="teachers")
    
    __mapper_args__ = {
        'polymorphic_identity': 'teacher',
    }
