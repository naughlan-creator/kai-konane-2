from config import db
from models.child import Level

class LearningPlan(db.Model):
    __tablename__ = 'learningPlan'

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'))
    science_level = db.Column(db.Enum(Level, name='science_level'))
    technology_level = db.Column(db.Enum(Level, name='technology_level'))
    engineering_level = db.Column(db.Enum(Level, name='engineering_level'))
    math_level = db.Column(db.Enum(Level, name='math_level'))
    story_level = db.Column(db.Enum(Level, name='story_level'))

    child = db.relationship("Child", back_populates="learning_plan")

    def get_level(self, stem_code):
        if stem_code == 'SCIENCE':
            return self.science_level
        elif stem_code == 'TECHNOLOGY':
            return self.technology_level
        elif stem_code == 'ENGINEERING':
            return self.engineering_level
        elif stem_code == 'MATH':
            return self.math_level
        else:
            return self.story_level