from config import db
from datetime import datetime
class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text(255), nullable=False)
    dateTime = db.Column(db.DateTime, default=datetime.utcnow)
    isRead = db.Column(db.Boolean, default=False)
    child_id = db.Column(db.Integer, db.ForeignKey('children.id'))

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_feedbacks')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_feedbacks')
    child = db.relationship('Child', foreign_keys=[child_id], back_populates='feedbacks')

    __mapper_args__ = {
        'polymorphic_identity': 'feedback',
    }

    def __init__(self, subject, message, sender_id, recipient_id, child_id=None):
        self.subject = subject
        self.message = message
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.child_id = child_id

