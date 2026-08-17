from app.config import db


class Answer(db.Model):
    __tablename__ = 'answer'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'),
                            nullable=False, index=True)

    question = db.relationship("Question", back_populates="answers")

    def __repr__(self):
        return f"<Answer {self.id} {self.content!r} correct={self.is_correct}>"
