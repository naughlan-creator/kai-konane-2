from config import db

class Preschool(db.Model):
    __tablename__ = 'preschools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    students = db.relationship("Child", back_populates="preschool")
    teachers = db.relationship("Teacher", back_populates="preschool")

    def __repr__(self):
        return f"<Preschool {self.id} {self.name!r}>"
