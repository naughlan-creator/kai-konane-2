from .user import User, Role
from config import db
from enum import Enum as PyEnum

class Level(PyEnum):
    BEGINNER = 'BEGINNER'
    INTERMEDIATE = 'INTERMEDIATE'
    ADVANCED = 'ADVANCED'

class LunchType(PyEnum):
    STANDARD = 'Standard'
    FREE_REDUCED = 'Free/Reduced'

class EducationLevel(PyEnum):
    SOME_HIGH_SCHOOL = 'some high school'
    HIGH_SCHOOL = 'high school'
    SOME_COLLEGE = 'some college'
    ASSOCIATES_DEGREE = 'associate\'s degree'
    BACHELORS_DEGREE = 'bachelor\'s degree'
    MASTERS_DEGREE = 'master\'s degree'

class Child(User):
    __tablename__ = 'children'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    preschool_id = db.Column(db.Integer, db.ForeignKey('preschools.id'))
    

    # New fields
    race_ethnicity = db.Column(db.String(50), nullable=True)
    lunch_type = db.Column(db.Enum(LunchType, name='lunch_type'), nullable=False)
    parent_education = db.Column(db.Enum(EducationLevel, name='parent_education'), nullable=False)
    recommended_level = db.Column(db.Enum(Level, name='recommended_level'), default=Level.BEGINNER)

    parent = db.relationship("Parent", back_populates="children", foreign_keys=[parent_id])
    teacher = db.relationship("Teacher", back_populates="students", foreign_keys=[teacher_id])
    preschool = db.relationship("Preschool", back_populates="students")
    progress = db.relationship("Progress", back_populates="child")
    results = db.relationship("Result", back_populates="child", cascade="all, delete-orphan")
    rewards = db.relationship("Reward", back_populates="child", cascade="all, delete-orphan")
    learning_plan = db.relationship("LearningPlan", back_populates="child", uselist=False)
    feedbacks = db.relationship('Feedback', back_populates='child')

    __mapper_args__ = {
        'polymorphic_identity': 'child',
    }
