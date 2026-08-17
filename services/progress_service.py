from sqlalchemy.orm import joinedload

from config import db as default_db
from models.child import Child
from models.progress import Progress


class ProgressService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_progress_by_child(self, child_id):
        # learning_content is embedded by the progress templates.
        return (Progress.query
                .options(joinedload(Progress.learning_content))
                .filter_by(child_id=child_id)
                .all())

    def get_progress_by_teacher(self, teacher_id):
        """Every learner's progress for one teacher, in one query."""
        return (Progress.query
                .options(joinedload(Progress.learning_content),
                         joinedload(Progress.child))
                .join(Child, Progress.child_id == Child.id)
                .filter(Child.teacher_id == teacher_id)
                .all())
