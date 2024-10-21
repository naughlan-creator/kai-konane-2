from config import db
from datetime import datetime

class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=False)
    score = db.Column(db.Float, default=0.0)
    date_acquired = db.Column(db.DateTime, default=datetime.utcnow)

    child = db.relationship("Child", back_populates="results")
    activity = db.relationship("Activity", back_populates="results")

    def __init__(self, activity_id, child_id, score=0.0):
        self.activity_id = activity_id
        self.child_id = child_id
        self.score = score