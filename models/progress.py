from config import db

class Progress(db.Model):
    __tablename__ = 'progress'

    id = db.Column(db.Integer, primary_key=True)
    completion_rate = db.Column(db.Float, default=0.0)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'), nullable=False)
    learning_content_id = db.Column(db.Integer, db.ForeignKey('learningContent.id'), nullable=False)

    child = db.relationship("Child", back_populates="progress")
    learning_content = db.relationship("LearningContent", back_populates="progress")

    def __init__(self, learning_content_id, child_id, completion_rate=0.0):
        self.learning_content_id = learning_content_id
        self.child_id = child_id
        self.completion_rate = completion_rate