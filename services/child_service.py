from config import db as default_db
from models.child import Child


class ChildService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_child(self, child_id):
        return self.db.session.get(Child, child_id)

    def get_children_of_parent(self, parent_id):
        return Child.query.filter_by(parent_id=parent_id).all()

    def get_students_of_teacher(self, teacher_id):
        return Child.query.filter_by(teacher_id=teacher_id).all()
