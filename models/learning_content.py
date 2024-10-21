from enum import Enum as PyEnum
from config import db

class LCTYPE(PyEnum):
    ACTIVITY = 'ACTIVITY'
    STORY = 'STORY'
    GAME = 'GAME'

class LearningContent(db.Model):
    __tablename__ = 'learningContent'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80))
    type = db.Column(db.Enum(LCTYPE, name='type'), nullable=False)

    progress = db.relationship("Progress", back_populates="learning_content")

    __mapper_args__ = {
        'polymorphic_identity': 'learning_content',
        'polymorphic_on': type
    }
