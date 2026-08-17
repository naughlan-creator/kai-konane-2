from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.config import db as default_db
from app.models.feedback import Feedback


class FeedbackService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_feedback(self, sender_id, recipient_id, subject, content, child_id=None):
        feedback = Feedback(subject=subject, message=content, sender_id=sender_id,
                            recipient_id=recipient_id, child_id=child_id)
        self.db.session.add(feedback)
        self.db.session.commit()
        return feedback

    def get_feedback(self, feedback_id):
        return self.db.session.get(Feedback, feedback_id)

    def get_unread_feedbacks_by_recipient_id(self, recipient_id):
        return (Feedback.query
                .options(joinedload(Feedback.sender))
                .filter_by(recipient_id=recipient_id, is_read=False)
                .order_by(Feedback.sent_at.desc())
                .all())

    def get_conversation(self, user_id, limit=100):
        """Everything sent and received, newest first, in one query."""
        return (Feedback.query
                .options(joinedload(Feedback.sender), joinedload(Feedback.recipient))
                .filter(or_(Feedback.sender_id == user_id,
                            Feedback.recipient_id == user_id))
                .order_by(Feedback.sent_at.desc())
                .limit(limit)
                .all())

    def mark_feedback_as_read(self, feedback_id):
        feedback = self.get_feedback(feedback_id)
        if feedback is None:
            return None
        feedback.is_read = True
        self.db.session.commit()
        return feedback
