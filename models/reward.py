from datetime import datetime

from config import db
from utils import utcdate


class Reward(db.Model):
    __tablename__ = 'rewards'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id', ondelete='CASCADE'),
                            nullable=True, index=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'),
                         nullable=True, index=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    content = db.Column(db.String(255), nullable=False)
    # Renamed from the misspelled dateAquired.
    date_acquired = db.Column(db.Date, default=utcdate, nullable=False)

    activity = db.relationship("Activity", back_populates="rewards")
    story = db.relationship("Story", back_populates="rewards")
    child = db.relationship("Child", back_populates="rewards")

    __table_args__ = (
        # A reward belongs to an activity or a story, never both and never neither.
        db.CheckConstraint(
            '(activity_id IS NOT NULL AND story_id IS NULL) OR '
            '(activity_id IS NULL AND story_id IS NOT NULL)',
            name='ck_reward_one_source'),
    )

    def __init__(self, child_id=None, content=None, activity_id=None, story_id=None,
                 date_acquired=None):
        # child_id first: the old signature started with activity_id, so every
        # positional call shifted the ids by one slot.
        self.child_id = child_id
        self.content = content
        self.activity_id = activity_id
        self.story_id = story_id
        if isinstance(date_acquired, datetime):
            date_acquired = date_acquired.date()
        self.date_acquired = date_acquired or utcdate()

    def __repr__(self):
        return f"<Reward {self.id} child={self.child_id} {self.content!r}>"
