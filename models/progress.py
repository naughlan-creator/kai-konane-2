from config import db


class Progress(db.Model):
    """How far a child has got through one piece of learning content."""
    __tablename__ = 'progress'

    id = db.Column(db.Integer, primary_key=True)
    completion_rate = db.Column(db.Float, default=0.0, nullable=False)
    total_num_questions = db.Column(db.Integer, default=0, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    learning_content_id = db.Column(db.Integer,
                                    db.ForeignKey('learning_content.id', ondelete='CASCADE'),
                                    nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('child_id', 'learning_content_id', name='uq_progress_child_content'),
    )

    child = db.relationship("Child", back_populates="progress")
    learning_content = db.relationship("LearningContent", back_populates="progress")

    def __init__(self, learning_content_id, child_id, completion_rate=0.0,
                 total_num_questions=0, completed=False):
        self.learning_content_id = learning_content_id
        self.child_id = child_id
        self.completion_rate = completion_rate
        self.total_num_questions = total_num_questions
        self.completed = completed

    def update_completion_rate(self, new_rate):
        self.completion_rate = max(0.0, min(100.0, float(new_rate)))
        if self.completion_rate >= 100:
            self.completed = True

    def mark_as_completed(self):
        self.completion_rate = 100.0
        self.completed = True

    def __repr__(self):
        return (f"<Progress child={self.child_id} content={self.learning_content_id} "
                f"{self.completion_rate}%>")
