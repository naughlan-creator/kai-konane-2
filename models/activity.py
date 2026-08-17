from enum import Enum as PyEnum

from config import db

from .child import LevelEnum
from .learning_content import LCTYPE, LearningContent


class StemCode(PyEnum):
    SCIENCE = 'SCIENCE'
    TECHNOLOGY = 'TECHNOLOGY'
    ENGINEERING = 'ENGINEERING'
    MATH = 'MATH'

    @classmethod
    def coerce(cls, value, default=None):
        if isinstance(value, cls):
            return value
        if value is None:
            return default
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            return default


class Activity(LearningContent):
    __tablename__ = 'activity'

    id = db.Column(db.Integer, db.ForeignKey('learning_content.id', ondelete='CASCADE'),
                   primary_key=True)
    # Every activity belongs to a STEM strand -- the learning plan is indexed by
    # it, so a NULL here silently hid the activity from recommendations.
    stem_code = db.Column(db.Enum(StemCode, name='stem_code'), nullable=False, index=True)
    level = db.Column(LevelEnum, nullable=False, index=True)
    cover_image = db.Column(db.String(255))

    questions = db.relationship("Question", back_populates="activity",
                                cascade="all, delete-orphan",
                                order_by="Question.position")
    rewards = db.relationship("Reward", back_populates="activity")
    results = db.relationship("Result", back_populates="activity",
                              cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': LCTYPE.ACTIVITY,
    }
