from models.teacher import Teacher
from config import db as default_db

class TeacherService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_teacher(self, teacher):
        self.db.session.add(teacher)
        self.db.session.commit()
        if self.get_teacher(teacher.id):
            return "Teacher added!!!"
        return "Teacher not added!!!"

    def get_teacher(self, teacher_id):
        return self.db.session.get(Teacher, teacher_id)

    def get_teachers(self):
        return Teacher.query.all()

    def update_teacher(self, teacher_id, firstname=None, lastname=None):
        existing_teacher = self.get_teacher(teacher_id)
        if not existing_teacher:
            return "Teacher not updated!!!"
        if firstname:
            existing_teacher.firstname = firstname
        if lastname:
            existing_teacher.lastname = lastname
        self.db.session.commit()
        return "Teacher updated!!!"

    def delete_teacher(self, teacher_id):
        teacher = self.get_teacher(teacher_id)
        if teacher:
            self.db.session.delete(teacher)
            self.db.session.commit()
            return "Teacher deleted!!!"
        return "Teacher not deleted!!!"

    def update_teacher_profile(self, teacher_id, firstname, lastname):
        teacher = self.get_teacher(teacher_id)
        if teacher:
            teacher.firstname = firstname
            teacher.lastname = lastname
            self.db.session.commit()
            return "Teacher profile updated successfully"
        return "Teacher not found"
