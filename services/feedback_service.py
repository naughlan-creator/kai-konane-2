from models.feedback import Feedback
from config import db as default_db
from datetime import datetime

class FeedbackService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_feedback(self, sender_id, recipient_id, subject, content, child_id=None):
        feedback = Feedback(subject=subject, message=content, sender_id=sender_id,
                            recipient_id=recipient_id, child_id=child_id)
        self.db.session.add(feedback)
        self.db.session.commit()
        return "Feedback added!"

    def get_feedback(self, feedback_id):
        return self.db.session.get(Feedback, feedback_id)

    def get_unread_feedbacks_by_recipient_id(self, recipient_id):
        """Only the messages still waiting to be read (the inbox)."""
        return (Feedback.query
                .filter_by(recipient_id=recipient_id, is_read=False)
                .order_by(Feedback.sent_at.desc())
                .all())

    def get_feedbacks_by_recipient_id(self, recipient_id):
        """Every message received, read or not (the history)."""
        return (Feedback.query
                .filter_by(recipient_id=recipient_id)
                .order_by(Feedback.sent_at.desc())
                .all())

    def get_feedbacks_by_sender_id(self, sender_id):
        return (Feedback.query
                .filter_by(sender_id=sender_id)
                .order_by(Feedback.sent_at.desc())
                .all())

    def get_feedbacks_by_child(self, child_id):
        return Feedback.query.filter_by(child_id=child_id).all()

    def mark_feedback_as_read(self, feedback_id):
        feedback = self.get_feedback(feedback_id)
        if feedback:
            feedback.is_read = True
            self.db.session.commit()
            return "Feedback marked as read!"
        return "Feedback not found!"

    def update_feedback(self, feedback_id, new_subject, new_content):
        feedback = self.get_feedback(feedback_id)
        if feedback:
            feedback.subject = new_subject
            feedback.message = new_content
            feedback.sent_at = datetime.utcnow()
            self.db.session.commit()
            return "Feedback updated!"
        return "Feedback not updated!"

    def delete_feedback(self, feedback_id):
        feedback = self.get_feedback(feedback_id)
        if feedback:
            self.db.session.delete(feedback)
            self.db.session.commit()
            return "Feedback deleted!"
        return "Feedback not deleted!"
