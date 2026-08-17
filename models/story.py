from config import db

from .child import LevelEnum
from .learning_content import LCTYPE, LearningContent


class Story(LearningContent):
    __tablename__ = 'story'

    id = db.Column(db.Integer, db.ForeignKey('learning_content.id', ondelete='CASCADE'),
                   primary_key=True)
    cover_page = db.Column(db.String(255))
    level = db.Column(LevelEnum, nullable=False, index=True)

    # Ordered explicitly: page order used to depend on insertion order of the
    # primary key, so re-saving a story could shuffle it.
    pages = db.relationship("Page", back_populates="story",
                            cascade="all, delete-orphan",
                            order_by="Page.page_number")
    rewards = db.relationship("Reward", back_populates="story")

    __mapper_args__ = {
        'polymorphic_identity': LCTYPE.STORY,
    }
