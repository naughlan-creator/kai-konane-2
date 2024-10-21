from models.parent import Parent
from models.child import Child

class ParentService:
    def __init__(self, db):
        self.db = db

    def add_parent(self, parent):
        self.db.session.add(parent)
        self.db.session.commit()
        if self.get_parent(parent.id):
            return "Parent added!!!"
        return "Parent not added!!!"

    def get_parent(self, parent_id):
        return Parent.query.get(parent_id)

    def get_parents():
        return Parent.query.all()

    def update_parent(self, parent):
        existing_parent = self.get_parent(parent.id)
        if existing_parent:
            existing_parent.name = parent.name
            self.db.session.commit()
            return "Parent updated!!!"
        return "Parent not updated!!!"

    def delete_parent(self, parent_id):
        parent = self.get_parent(parent_id)
        if parent:
            self.db.session.delete(parent)
            self.db.session.commit()
            return "Parent deleted!!!"
        return "Parent not deleted!!!"
    
    def update_parent_profile(self, parent_id, firstname, lastname, education_level):
        parent = self.get_parent(parent_id)
        if parent:
            parent.firstname = firstname
            parent.lastname = lastname
            parent.education_level = education_level
            self.db.session.commit()
            return "Parent profile updated successfully"
        return "Parent not found"

    def update_child_profile(self, child_id, firstname, lastname, age, gender, race_ethnicity, lunch_type):
        child = Child.query.get(child_id)
        if child:
            child.firstname = firstname
            child.lastname = lastname
            child.age = age
            child.gender = gender
            child.race_ethnicity = race_ethnicity
            child.lunch_type = lunch_type
            self.db.session.commit()
            return "Child profile updated successfully"
        return "Child not found"