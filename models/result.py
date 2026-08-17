from config import db
from utils import utcnow


class Result(db.Model):
    """One recorded attempt at an activity.

    This is an append-only log: a child may attempt the same activity many
    times. Code that needs "the latest score" should order by date_acquired
    rather than assume a single row per (child, activity).
    """
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    score = db.Column(db.Float, default=0.0, nullable=False)
    date_acquired = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    child = db.relationship("Child", back_populates="results")
    activity = db.relationship("Activity", back_populates="results")

    def __init__(self, child_id=None, activity_id=None, score=0.0, date_acquired=None):
        # child_id first, matching every other model; the old order was
        # (activity_id, child_id) and callers routinely got it backwards.
        self.child_id = child_id
        self.activity_id = activity_id
        self.score = score
        self.date_acquired = date_acquired or utcnow()

    def __repr__(self):
        return f"<Result {self.id} child={self.child_id} activity={self.activity_id} {self.score}>"
