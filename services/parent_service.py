from models.parent import Parent
from models.child import Child, EducationLevel, LunchType
from config import db as default_db

class ParentService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_parent(self, parent):
        self.db.session.add(parent)
        self.db.session.commit()
        if self.get_parent(parent.id):
            return "Parent added!!!"
        return "Parent not added!!!"

    def get_parent(self, parent_id):
        return self.db.session.get(Parent, parent_id)

    def get_parents(self):
        return Parent.query.all()

    def update_parent(self, parent_id, firstname=None, lastname=None):
        existing_parent = self.get_parent(parent_id)
        if not existing_parent:
            return "Parent not updated!!!"
        if firstname:
            existing_parent.firstname = firstname
        if lastname:
            existing_parent.lastname = lastname
        self.db.session.commit()
        return "Parent updated!!!"

    def delete_parent(self, parent_id):
        parent = self.get_parent(parent_id)
        if parent:
            self.db.session.delete(parent)
            self.db.session.commit()
            return "Parent deleted!!!"
        return "Parent not deleted!!!"

    def update_parent_profile(self, parent_id, firstname, lastname, education_level):
        parent = self.get_parent(parent_id)
        if not parent:
            return "Parent not found"

        level = EducationLevel.coerce(education_level, parent.education_level)
        if level is None:
            return "Please choose a valid education level"

        parent.firstname = firstname
        parent.lastname = lastname
        parent.education_level = level
        # The child model snapshots the parent's education for the level model,
        # so keep the two in sync.
        for child in parent.children:
            child.parent_education = level
        self.db.session.commit()
        return "Parent profile updated successfully"

    def update_child_profile(self, child_id, firstname, lastname, age, gender, race_ethnicity, lunch_type):
        child = self.db.session.get(Child, child_id)
        if not child:
            return "Child not found"

        lunch = LunchType.coerce(lunch_type, child.lunch_type)
        if lunch is None:
            return "Please choose a valid lunch type"

        try:
            child.age = int(age)
        except (TypeError, ValueError):
            return "Age must be a whole number"

        child.firstname = firstname
        child.lastname = lastname
        child.gender = gender
        child.race_ethnicity = race_ethnicity
        child.lunch_type = lunch
        self.db.session.commit()
        return "Child profile updated successfully"
