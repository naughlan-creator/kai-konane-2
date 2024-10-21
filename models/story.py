from .learning_content import LearningContent, LCTYPE
from config import db
from .child import Level

class Story(LearningContent):
    __tablename__ = 'story'

    id = db.Column(db.Integer, db.ForeignKey('learningContent.id'), primary_key=True)
    cover_page = db.Column(db.String(255))
    level = db.Column(db.Enum(Level, name='level'), nullable=False)
    pages = db.relationship("Page", back_populates="story", cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': LCTYPE.STORY,
    }
