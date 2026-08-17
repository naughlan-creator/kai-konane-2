from enum import Enum as PyEnum

from config import db


class LCTYPE(PyEnum):
    ACTIVITY = 'ACTIVITY'
    STORY = 'STORY'
    GAME = 'GAME'

class LearningContent(db.Model):
    # snake_case: the old name "learningContent" is a quoted, case-sensitive
    # identifier in Postgres, so any hand-written SQL against it had to quote it
    # exactly or fail.
    __tablename__ = 'learning_content'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    type = db.Column(db.Enum(LCTYPE, name='lc_type'), nullable=False, index=True)

    progress = db.relationship("Progress", back_populates="learning_content",
                               cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': 'learning_content',
        'polymorphic_on': type
    }

    def __repr__(self):
        return f"<{type(self).__name__} {self.id} {self.title!r}>"
