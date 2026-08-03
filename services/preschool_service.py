from models.preschool import Preschool
from config import db as default_db

class PreschoolService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_preschool(self, preschool):
        self.db.session.add(preschool)
        self.db.session.commit()
        if self.get_preschool(preschool.id):
            return "Preschool added!!!"
        return "Preschool not added!!!"

    @staticmethod
    def get_preschool(preschool_id):
        return default_db.session.get(Preschool, preschool_id)

    @staticmethod
    def get_preschools():
        return Preschool.query.order_by(Preschool.name).all()

    def update_preschool(self, preschool):
        existing_preschool = self.get_preschool(preschool.id)
        if existing_preschool:
            existing_preschool.name = preschool.name
            self.db.session.commit()
            return "Preschool updated!!!"
        return "Preschool not updated!!!"

    def delete_preschool(self, preschool_id):
        preschool = self.get_preschool(preschool_id)
        if not preschool:
            return "Preschool not deleted!!!"
        if preschool.students or preschool.teachers:
            return "Preschool still has teachers or learners assigned to it!!!"
        self.db.session.delete(preschool)
        self.db.session.commit()
        return "Preschool deleted!!!"
