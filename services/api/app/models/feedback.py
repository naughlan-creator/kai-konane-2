from app.config import db
from app.utils import utcnow


class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                             nullable=False, index=True)
    subject = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    # Renamed from dateTime / isRead: everything else in the schema is snake_case.
    sent_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id', ondelete='CASCADE'),
                         index=True)

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_feedbacks')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_feedbacks')
    child = db.relationship('Child', foreign_keys=[child_id], back_populates='feedbacks')

    def __init__(self, subject, message, sender_id, recipient_id, child_id=None, sent_at=None):
        self.subject = subject
        self.message = message
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.child_id = child_id
        self.sent_at = sent_at or utcnow()

    def __repr__(self):
        return f"<Feedback {self.id} {self.sender_id}->{self.recipient_id} {self.subject!r}>"
