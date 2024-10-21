from models.child import Child
from config import db

class ChildService:
    def __init__(self):
        self.db = db

    def add_child(self, child):
        self.db.session.add(child)
        self.db.session.commit()
        if self.get_child(child.id):
            return "Child added!!!"
        return "Child not added!!!"

    def get_child(self, child_id):
        return Child.query.get(child_id)

    def get_children(self):
        return Child.query.all()

    def update_child(self, child):
        existing_child = self.get_child(child.id)
        if existing_child:
            existing_child.name = child.name
            self.db.session.commit()
            return "Child updated!!!"
        return "Child not updated!!!"

    def delete_child(self, child_id):
        child = self.get_child(child_id)
        if child:
            self.db.session.delete(child)
            self.db.session.commit()
            return "Child deleted!!!"
        return "Child not deleted!!!"