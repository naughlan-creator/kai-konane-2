from app.config import db as default_db
from app.models.preschool import Preschool
from app.services.errors import Conflict, NotFound, ValidationError


class PreschoolService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_preschool(self, preschool_id):
        return self.db.session.get(Preschool, preschool_id)

    def get_preschools(self):
        return Preschool.query.order_by(Preschool.name).all()

    def _require(self, preschool_id):
        preschool = self.get_preschool(preschool_id)
        if preschool is None:
            raise NotFound("That preschool no longer exists")
        return preschool

    @staticmethod
    def _clean_name(name):
        name = (name or "").strip()
        if not name:
            raise ValidationError("Please enter a preschool name")
        return name

    def add_preschool(self, name):
        name = self._clean_name(name)
        if Preschool.query.filter_by(name=name).first():
            raise Conflict("A preschool with that name already exists")

        preschool = Preschool(name=name)
        self.db.session.add(preschool)
        self.db.session.commit()
        return preschool

    def update_preschool(self, preschool_id, name):
        preschool = self._require(preschool_id)
        name = self._clean_name(name)
        if Preschool.query.filter(Preschool.name == name,
                                  Preschool.id != preschool_id).first():
            raise Conflict("A preschool with that name already exists")

        preschool.name = name
        self.db.session.commit()
        return preschool

    def delete_preschool(self, preschool_id):
        preschool = self._require(preschool_id)
        if preschool.students or preschool.teachers:
            raise Conflict("Move the teachers and learners out of this preschool first")

        self.db.session.delete(preschool)
        self.db.session.commit()
        return preschool
