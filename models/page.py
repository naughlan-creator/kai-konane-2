from config import db


class Page(db.Model):
    __tablename__ = 'page'

    id = db.Column(db.Integer, primary_key=True)
    # A page of a picture book is often more than 100 characters.
    line_of_page = db.Column(db.String(500), nullable=False)
    image_filename = db.Column(db.String(255))
    # Explicit page order rather than whatever order the rows happen to come
    # back in.
    page_number = db.Column(db.Integer, nullable=False, default=1)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'),
                         nullable=False, index=True)

    story = db.relationship("Story", back_populates="pages")

    __table_args__ = (
        db.UniqueConstraint('story_id', 'page_number', name='uq_page_story_number'),
    )

    @property
    def is_last_page(self):
        """Derived from position instead of a flag that could contradict it."""
        if not self.story:
            return True
        return self.page_number >= max(page.page_number for page in self.story.pages)

    def __repr__(self):
        return f"<Page {self.id} story={self.story_id} #{self.page_number}>"
