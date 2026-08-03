from config import db
from models.child import Level, LevelEnum

# The learning plan column that backs each STEM strand.
STRAND_FIELDS = {
    'SCIENCE': 'science_level',
    'TECHNOLOGY': 'technology_level',
    'ENGINEERING': 'engineering_level',
    'MATH': 'math_level',
    'STORY': 'story_level',
}


class LearningPlan(db.Model):
    __tablename__ = 'learning_plans'

    id = db.Column(db.Integer, primary_key=True)
    # One plan per child, enforced by the database rather than by hope.
    child_id = db.Column(db.Integer, db.ForeignKey('children.id', ondelete='CASCADE'),
                         nullable=False, unique=True, index=True)
    science_level = db.Column(LevelEnum, nullable=False, default=Level.BEGINNER)
    technology_level = db.Column(LevelEnum, nullable=False, default=Level.BEGINNER)
    engineering_level = db.Column(LevelEnum, nullable=False, default=Level.BEGINNER)
    math_level = db.Column(LevelEnum, nullable=False, default=Level.BEGINNER)
    story_level = db.Column(LevelEnum, nullable=False, default=Level.BEGINNER)

    child = db.relationship("Child", back_populates="learning_plan")

    def get_level(self, stem_code):
        """The level for one strand.

        Accepts a StemCode, a string, or None. The old version compared the
        argument to string literals, so passing a StemCode enum fell through
        every branch and silently returned story_level.
        """
        if stem_code is None:
            return None
        name = getattr(stem_code, 'name', None) or str(stem_code)
        field = STRAND_FIELDS.get(name.strip().upper())
        if field is None:
            return None
        return getattr(self, field)

    def set_level(self, stem_code, level):
        name = getattr(stem_code, 'name', None) or str(stem_code)
        field = STRAND_FIELDS.get(name.strip().upper())
        if field is not None:
            setattr(self, field, level)
        return self

    def as_dict(self):
        return {strand.lower(): getattr(self, field).name
                for strand, field in STRAND_FIELDS.items()}

    def __repr__(self):
        return f"<LearningPlan child={self.child_id} {self.as_dict()}>"
