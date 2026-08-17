from config import db as default_db
from models.child import Child


class ChildService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_child(self, child_id):
        return self.db.session.get(Child, child_id)
