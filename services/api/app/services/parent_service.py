from app.config import db as default_db
from app.models.child import Child, EducationLevel, LunchType
from app.models.parent import Parent
from app.services.errors import NotFound, ValidationError


class ParentService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_parent(self, parent_id):
        return self.db.session.get(Parent, parent_id)

    def update_parent_profile(self, parent_id, firstname, lastname, education_level):
        parent = self.get_parent(parent_id)
        if parent is None:
            raise NotFound("That parent no longer exists")

        # "Not supplied" and "supplied but wrong" are different. Passing the
        # current value as coerce()'s default collapses them, so a typo silently
        # kept the old level and the form reported success -- the caller had no
        # way to know their choice was discarded.
        if education_level in (None, ''):
            level = parent.education_level
        else:
            level = EducationLevel.coerce(education_level)
            if level is None:
                raise ValidationError("Please choose a valid education level")

        parent.firstname = firstname
        parent.lastname = lastname
        parent.education_level = level
        # Child snapshots the parent's education for the level model, so the
        # two must move together or predictions drift from reality.
        for child in parent.children:
            child.parent_education = level

        self.db.session.commit()
        return parent

    def update_child_profile(self, child_id, firstname, lastname, age, gender,
                             race_ethnicity, lunch_type):
        child = self.db.session.get(Child, child_id)
        if child is None:
            raise NotFound("That learner no longer exists")

        if lunch_type in (None, ''):
            lunch = child.lunch_type
        else:
            lunch = LunchType.coerce(lunch_type)
            if lunch is None:
                raise ValidationError("Please choose a valid lunch type")

        try:
            child.age = int(age)
        except (TypeError, ValueError):
            raise ValidationError("Age must be a whole number") from None

        child.firstname = firstname
        child.lastname = lastname
        child.gender = gender
        child.race_ethnicity = race_ethnicity
        child.lunch_type = lunch

        self.db.session.commit()
        return child
