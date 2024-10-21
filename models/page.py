from config import db

class Page(db.Model):
    __tablename__ = 'page'

    id = db.Column(db.Integer, primary_key=True)
    line_of_page = db.Column(db.String(100), nullable=False)
    image_filename = db.Column(db.String(255))
    is_last_page = db.Column(db.Boolean, nullable=False)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'))

    story = db.relationship("Story", back_populates="pages")
