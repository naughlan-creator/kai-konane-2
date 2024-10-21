from datetime import datetime
from config import db

class Reward(db.Model):
    __tablename__ = 'rewards'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'), nullable=False)
    content = db.Column(db.String(255))
    dateAquired = db.Column(db.Date, default=datetime.utcnow)

    activity = db.relationship("Activity", back_populates="rewards")
    child = db.relationship("Child", back_populates="rewards")

    def __init__(self, activity_id=None, story_id=None, child_id=None, content=None, dateAquired=None):
        self.activity_id = activity_id
        self.child_id = child_id
        self.story_id = story_id
        self.content = content
        self.dateAquired = dateAquired