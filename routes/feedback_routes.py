from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.feedback import Feedback
from models.user import User, Role
from models.child import Child
from services.feedback_service import FeedbackService
from routes.auth import roles_required
from config import db

feedback_bp = Blueprint('feedback', __name__, url_prefix='/feedbacks')

feedback_service = FeedbackService()

# Only parents and teachers exchange feedback.
correspondent_required = roles_required(Role.PARENT, Role.TEACHER)


def _children_for(user):
    """The learners this user may attach feedback to."""
    if user.role == Role.PARENT:
        return Child.query.filter_by(parent_id=user.id).all()
    if user.role == Role.TEACHER:
        return Child.query.filter_by(teacher_id=user.id).all()
    return []


@feedback_bp.route('/feedback')
@correspondent_required
def feedback_home():
    return render_template('FeedbackSystem/feedback_home.html')

@feedback_bp.route('/home')
@login_required
def home():
    # Previously returned None (and so a 500) for admins and children.
    return redirect(url_for('user.home'))

@feedback_bp.route('/feedback/write')
@correspondent_required
def write_feedback():
    recipient_id = request.args.get('recipient_id')
    if recipient_id:
        return render_template('FeedbackSystem/write_feedback.html',
                               recipient_id=recipient_id,
                               children=_children_for(current_user))

    if current_user.role == Role.PARENT:
        recipients = User.query.filter_by(role=Role.TEACHER).all()
    else:
        recipients = User.query.filter_by(role=Role.PARENT).all()
    return render_template('FeedbackSystem/select_feedback_receiver.html',
                           recipients=recipients,
                           user_role=current_user.role.name)

@feedback_bp.route('/feedback/submit', methods=['POST'])
@correspondent_required
def submit_feedback():
    # request.form['child_id'] raised a KeyError whenever the form had no
    # learner attached; an empty string then broke the foreign key.
    recipient_id = request.form.get('recipient_id')
    subject = (request.form.get('subject') or '').strip()
    content = (request.form.get('content') or '').strip()
    child_id = request.form.get('child_id') or None

    if not recipient_id or not subject or not content:
        flash("Please fill in a subject and a message", "error")
        return redirect(url_for('feedback.write_feedback', recipient_id=recipient_id))

    recipient = db.session.get(User, int(recipient_id)) if str(recipient_id).isdigit() else None
    if recipient is None or recipient.role not in (Role.PARENT, Role.TEACHER):
        flash("That recipient does not exist", "error")
        return redirect(url_for('feedback.write_feedback'))

    if child_id is not None:
        allowed_ids = {child.id for child in _children_for(current_user)}
        if int(child_id) not in allowed_ids:
            flash("You can only send feedback about your own learners", "error")
            return redirect(url_for('feedback.write_feedback'))

    feedback_service.add_feedback(current_user.id, recipient.id, subject, content, child_id)
    flash("Feedback sent successfully")
    return redirect(url_for('feedback.feedback_home'))

@feedback_bp.route('/feedback/view')
@correspondent_required
def view_feedback():
    # The inbox: only what has not been read yet.
    feedbacks = feedback_service.get_unread_feedbacks_by_recipient_id(current_user.id)
    return render_template('FeedbackSystem/view_feedback.html', feedbacks=feedbacks)

@feedback_bp.route('/feedback/past')
@correspondent_required
def past_feedback():
    # The history: everything sent and everything received, read or not. This
    # used to filter received messages to isRead=False, so a message vanished
    # from the history the moment it was opened.
    sent_feedbacks = feedback_service.get_feedbacks_by_sender_id(current_user.id)
    received_feedbacks = feedback_service.get_feedbacks_by_recipient_id(current_user.id)
    all_feedbacks = sent_feedbacks + received_feedbacks
    all_feedbacks.sort(key=lambda x: x.sent_at, reverse=True)
    return render_template('FeedbackSystem/past_feedback.html', feedbacks=all_feedbacks)

@feedback_bp.route('/feedback/read/<int:feedback_id>')
@login_required
def read_feedback(feedback_id):
    feedback = feedback_service.get_feedback(feedback_id)
    if feedback and (feedback.recipient_id == current_user.id or feedback.sender_id == current_user.id):
        if feedback.recipient_id == current_user.id:
            feedback_service.mark_feedback_as_read(feedback_id)
        return render_template('FeedbackSystem/read_feedback.html', feedback=feedback)

    flash("You don't have permission to read this feedback")
    return redirect(url_for('feedback.view_feedback'))
