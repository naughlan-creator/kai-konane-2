from app.config import db as default_db
from app.models.teacher import Teacher
from app.services.errors import NotFound


class TeacherService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_teacher(self, teacher_id):
        return self.db.session.get(Teacher, teacher_id)

    def get_teachers(self):
        return Teacher.query.order_by(Teacher.lastname, Teacher.firstname).all()

    def update_teacher_profile(self, teacher_id, firstname, lastname):
        teacher = self.get_teacher(teacher_id)
        if teacher is None:
            raise NotFound("That teacher no longer exists")

        teacher.firstname = firstname
        teacher.lastname = lastname
        self.db.session.commit()
        return teacher
