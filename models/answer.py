from config import db

class Answer(db.Model):
    __tablename__ = 'answer'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(80))
    is_correct = db.Column(db.Boolean)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))

    question = db.relationship("Question", back_populates="answers")
