from models.admin import Admin
from config import db as default_db

class AdministratorService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_admin(self, admin):
        self.db.session.add(admin)
        self.db.session.commit()
        if self.get_admin(admin.id):
            return "Administrator added!!!"
        return "Administrator not added!!!"

    def get_admin(self, admin_id):
        return self.db.session.get(Admin, admin_id)

    def get_admins(self):
        return Admin.query.all()

    def update_admin(self, admin_id, name):
        existing_admin = self.get_admin(admin_id)
        if existing_admin:
            existing_admin.name = name
            self.db.session.commit()
            return "Administrator updated!!!"
        return "Administrator not updated!!!"

    def delete_admin(self, admin_id):
        admin = self.get_admin(admin_id)
        if admin:
            self.db.session.delete(admin)
            self.db.session.commit()
            return "Administrator deleted!!!"
        return "Administrator not deleted!!!"
