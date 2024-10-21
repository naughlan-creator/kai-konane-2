from models.feedback import Feedback
from config import db
from datetime import datetime

class FeedbackService:
    def __init__(self):
        self.db = db

    def add_feedback(self, sender_id, recipient_id, subject, content, child_id=None):
        feedback = Feedback(subject=subject, message=content, sender_id=sender_id, recipient_id=recipient_id, child_id=child_id)
        self.db.session.add(feedback)
        self.db.session.commit()
        return "Feedback added!"

    def get_feedback(self, feedback_id):
        return Feedback.query.get(feedback_id)

    def get_feedbacks_by_recipient_id(self, recipient_id):
        return Feedback.query.filter_by(recipient_id=recipient_id, isRead=False).all()

    def get_feedbacks_by_sender_id(self, sender_id):
        return Feedback.query.filter_by(sender_id=sender_id).all()
    
    def get_feedbacks_by_child(self, child_id):
        return Feedback.query.filter_by(child_id=child_id).all()

    def mark_feedback_as_read(self, feedback_id):
        feedback = self.get_feedback(feedback_id)
        if feedback:
            feedback.isRead = True
            self.db.session.commit()
            return "Feedback marked as read!"
        return "Feedback not found!"

    def update_feedback(self, feedback_id, new_subject, new_content):
        feedback = self.get_feedback(feedback_id)
        if feedback:
            feedback.subject = new_subject
            feedback.message = new_content  # Changed from content to message
            feedback.dateTime = datetime.utcnow()  # Updated to match the model
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