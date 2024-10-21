from models.preschool import Preschool

class PreschoolService:
    def __init__(self, db):
        self.db = db

    def add_preschool(self, preschool):
        self.db.session.add(preschool)
        self.db.session.commit()
        if self.get_preschool(preschool.id):
            return "Preschool added!!!"
        return "Preschool not added!!!"

    @staticmethod
    def get_preschool(preschool_id):
        return Preschool.query.get(preschool_id)

    @staticmethod
    def get_preschools():
        return Preschool.query.all()

    def update_preschool(self, preschool):
        existing_preschool = self.get_preschool(preschool.id)
        if existing_preschool:
            existing_preschool.name = preschool.name
            self.db.session.commit()
            return "Preschool updated!!!"
        return "Preschool not updated!!!"

    def delete_preschool(self, preschool_id):
        preschool = self.get_preschool(preschool_id)
        if preschool:
            self.db.session.delete(preschool)
            self.db.session.commit()
            return "Preschool deleted!!!"
        return "Preschool not deleted!!!"