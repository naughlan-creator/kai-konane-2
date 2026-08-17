from sqlalchemy.orm import joinedload

from app.config import db as default_db
from app.models.child import Child
from app.models.result import Result


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

    def get_stem_levels(self, child_id):
        """Mean score per STEM strand for one child, strands with no attempts
        reported as 0.

        Moved out of the route because the gateway forwards /api/* to this
        service: the old `/api/child_stem_levels/<id>` on the web side became
        unreachable the moment nginx sat in front of it.
        """
        from sqlalchemy import func

        from app.models.activity import Activity, StemCode

        rows = (self.db.session.query(Activity.stem_code,
                                      func.avg(Result.score).label('avg_score'))
                .join(Result, Result.activity_id == Activity.id)
                .filter(Result.child_id == child_id)
                .group_by(Activity.stem_code)
                .all())

        levels = {code.name.lower(): 0 for code in StemCode}
        for stem_code, average in rows:
            if stem_code is not None and average is not None:
                levels[stem_code.name.lower()] = round(average, 2)
        return levels

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
