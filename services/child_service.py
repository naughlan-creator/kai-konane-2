from models.child import Child
from config import db as default_db

class ChildService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_child(self, child):
        self.db.session.add(child)
        self.db.session.commit()
        if self.get_child(child.id):
            return "Child added!!!"
        return "Child not added!!!"

    def get_child(self, child_id):
        return self.db.session.get(Child, child_id)

    def get_children(self):
        return Child.query.all()

    def update_child(self, child_id, firstname=None, lastname=None, age=None):
        existing_child = self.get_child(child_id)
        if not existing_child:
            return "Child not updated!!!"
        if firstname:
            existing_child.firstname = firstname
        if lastname:
            existing_child.lastname = lastname
        if age is not None:
            existing_child.age = int(age)
        self.db.session.commit()
        return "Child updated!!!"

    def delete_child(self, child_id):
        child = self.get_child(child_id)
        if child:
            self.db.session.delete(child)
            self.db.session.commit()
            return "Child deleted!!!"
        return "Child not deleted!!!"
