from config import db

class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(80))
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'))

    activity = db.relationship("Activity", back_populates="questions")
    answers = db.relationship("Answer", back_populates="question", cascade="all, delete-orphan")
