from config import db

class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True)
    # 80 chars is not enough for a real question.
    content = db.Column(db.String(255), nullable=False)
    # Explicit ordering: relying on the primary key meant an edited question
    # jumped to the end of the activity.
    position = db.Column(db.Integer, nullable=False, default=0)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id', ondelete='CASCADE'),
                            nullable=False, index=True)

    activity = db.relationship("Activity", back_populates="questions")
    answers = db.relationship("Answer", back_populates="question",
                              cascade="all, delete-orphan",
                              order_by="Answer.position")

    @property
    def correct_answer(self):
        return next((answer for answer in self.answers if answer.is_correct), None)

    def __repr__(self):
        return f"<Question {self.id} {self.content!r}>"
