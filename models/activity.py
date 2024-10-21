from .learning_content import LearningContent, LCTYPE
from enum import Enum as PyEnum
from .child import Level
from config import db

class StemCode(PyEnum):
    SCIENCE = 'SCIENCE'
    TECHNOLOGY = 'TECHNOLOGY'
    ENGINEERING = 'ENGINEERING'
    MATH = 'MATH'


class Activity(LearningContent):
    __tablename__ = 'activity'

    id = db.Column(db.Integer, db.ForeignKey('learningContent.id'), primary_key=True)
    stem_code = db.Column(db.Enum(StemCode, name='stem_code'))
    level = db.Column(db.Enum(Level, name='level'), nullable=False)
    cover_image = db.Column(db.String(255))

    questions = db.relationship("Question", back_populates="activity", cascade="all, delete-orphan")
    rewards = db.relationship("Reward", back_populates="activity")
    results = db.relationship("Result", back_populates="activity")

    __mapper_args__ = {
        'polymorphic_identity': LCTYPE.ACTIVITY,
    }
