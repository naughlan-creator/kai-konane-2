from enum import Enum as PyEnum

from app.config import db

from .user import User


class Level(PyEnum):
    BEGINNER = 'BEGINNER'
    INTERMEDIATE = 'INTERMEDIATE'
    ADVANCED = 'ADVANCED'

    @property
    def rank(self):
        """Position in the beginner -> advanced ordering.

        The enum *values* are strings, so never sort or compare on ``.value``:
        alphabetically ADVANCED sorts before BEGINNER.
        """
        return LEVEL_ORDER.index(self)

    def shifted(self, delta):
        """Return the level ``delta`` steps away, clamped to the valid range."""
        index = min(max(self.rank + delta, 0), len(LEVEL_ORDER) - 1)
        return LEVEL_ORDER[index]

    @classmethod
    def coerce(cls, value, default=None):
        """Build a Level from a Level, a name or a value; ``default`` on failure."""
        if isinstance(value, cls):
            return value
        if value is None:
            return default
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            try:
                return cls(str(value).strip().upper())
            except ValueError:
                return default


LEVEL_ORDER = [Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED]

# One shared database type for every level column. Previously each column
# declared its own ("science_level", "math_level", "recommended_level", ...),
# which meant seven identical enum types in Postgres to keep in step.
LevelEnum = db.Enum(Level, name='content_level', metadata=db.metadata)

class _CoercibleEnum(PyEnum):
    """Enum that accepts either a member name or a member value from a form."""

    @classmethod
    def coerce(cls, value, default=None):
        if isinstance(value, cls):
            return value
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        try:
            return cls(text)
        except ValueError:
            pass
        for member in cls:
            if member.name.lower() == text.lower() or member.value.lower() == text.lower():
                return member
        return default


class LunchType(_CoercibleEnum):
    STANDARD = 'Standard'
    FREE_REDUCED = 'Free/Reduced'

class EducationLevel(_CoercibleEnum):
    SOME_HIGH_SCHOOL = 'some high school'
    HIGH_SCHOOL = 'high school'
    SOME_COLLEGE = 'some college'
    ASSOCIATES_DEGREE = 'associate\'s degree'
    BACHELORS_DEGREE = 'bachelor\'s degree'
    MASTERS_DEGREE = 'master\'s degree'

class Child(User):
    __tablename__ = 'children'

    id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='SET NULL'),
                           index=True)
    preschool_id = db.Column(db.Integer, db.ForeignKey('preschools.id', ondelete='SET NULL'),
                             index=True)

    race_ethnicity = db.Column(db.String(50), nullable=True)
    lunch_type = db.Column(db.Enum(LunchType, name='lunch_type'), nullable=False)
    parent_education = db.Column(db.Enum(EducationLevel, name='parent_education'), nullable=False)
    recommended_level = db.Column(LevelEnum, default=Level.BEGINNER, nullable=False)

    parent = db.relationship("Parent", back_populates="children", foreign_keys=[parent_id])
    teacher = db.relationship("Teacher", back_populates="students", foreign_keys=[teacher_id])
    preschool = db.relationship("Preschool", back_populates="students")
    # Deleting a child now takes its dependent rows with it, instead of leaving
    # the caller to clear each table by hand before the delete.
    progress = db.relationship("Progress", back_populates="child",
                               cascade="all, delete-orphan")
    results = db.relationship("Result", back_populates="child", cascade="all, delete-orphan")
    rewards = db.relationship("Reward", back_populates="child", cascade="all, delete-orphan")
    learning_plan = db.relationship("LearningPlan", back_populates="child", uselist=False,
                                    cascade="all, delete-orphan")
    feedbacks = db.relationship('Feedback', back_populates='child',
                                cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': 'child',
    }

    @property
    def fullname(self):
        return f"{self.firstname} {self.lastname}".strip()

    def level_for(self, stem_code):
        """The child's level in one STEM strand, from their learning plan."""
        if self.learning_plan is not None:
            return self.learning_plan.get_level(stem_code) or self.recommended_level
        return self.recommended_level
