from sqlalchemy.orm import joinedload

from config import db as default_db
from models.child import Child
from models.result import Result


class ResultService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_results_by_child(self, child_id):
        # activity is embedded by the results templates (activity.title,
        # activity.stem_code), so load it up front rather than per row.
        return (Result.query
                .options(joinedload(Result.activity))
                .filter_by(child_id=child_id)
                .order_by(Result.date_acquired.desc())
                .all())

    def get_results_by_teacher(self, teacher_id):
        """Every attempt by every learner of one teacher, in one query.

        The previous version ran a query per child and concatenated in Python,
        which also lost the global ordering.
        """
        return (Result.query
                .options(joinedload(Result.activity), joinedload(Result.child))
                .join(Child, Result.child_id == Child.id)
                .filter(Child.teacher_id == teacher_id)
                .order_by(Result.date_acquired.desc())
                .all())
