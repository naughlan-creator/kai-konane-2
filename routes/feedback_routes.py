from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.feedback import Feedback
from models.user import User, Role
from models.child import Child
from services.feedback_service import FeedbackService

feedback_bp = Blueprint('feedback', __name__, url_prefix='/feedbacks')

feedback_service = FeedbackService()

@feedback_bp.route('/feedback')
@login_required
def feedback_home():
    return render_template('FeedbackSystem/feedback_home.html')

@feedback_bp.route('/home')
@login_required
def home():
    if current_user.role == Role.TEACHER:
        return redirect(url_for('user.teacher_home'))
    elif current_user.role == Role.PARENT:
        return redirect(url_for('user.parent_home'))

@feedback_bp.route('/feedback/write')
@login_required
def write_feedback():
    recipient_id = request.args.get('recipient_id')
    if recipient_id:
        children = Child.query.filter_by(parent_id=current_user.id).all() if current_user.role == Role.PARENT else Child.query.filter_by(teacher_id=current_user.id).all()
        return render_template('FeedbackSystem/write_feedback.html', recipient_id=recipient_id, children=children)
    else:
        if current_user.role == Role.PARENT:
            recipients = User.query.filter_by(role=Role.TEACHER).all()
        elif current_user.role == Role.TEACHER:
            recipients = User.query.filter_by(role=Role.PARENT).all()
        else:
            flash("You don't have permission to send feedback")
            return redirect(url_for('feedback.home'))
        return render_template('FeedbackSystem/select_feedback_receiver.html', recipients=recipients, user_role=current_user.role.name)

@feedback_bp.route('/feedback/submit', methods=['POST'])
@login_required
def submit_feedback():
    recipient_id = request.form['recipient_id']
    subject = request.form['subject']
    content = request.form['content']
    child_id = request.form['child_id']
    feedback_service.add_feedback(current_user.id, recipient_id, subject, content, child_id)
    flash("Feedback sent successfully")
    return redirect(url_for('feedback.feedback_home'))

@feedback_bp.route('/feedback/view')
@login_required
def view_feedback():
    feedbacks = feedback_service.get_feedbacks_by_recipient_id(current_user.id)
    return render_template('FeedbackSystem/view_feedback.html', feedbacks=feedbacks)

@feedback_bp.route('/feedback/past')
@login_required
def past_feedback():
    sent_feedbacks = feedback_service.get_feedbacks_by_sender_id(current_user.id)
    received_feedbacks = feedback_service.get_feedbacks_by_recipient_id(current_user.id)
    all_feedbacks = sent_feedbacks + received_feedbacks
    all_feedbacks.sort(key=lambda x: x.dateTime, reverse=True)
    return render_template('FeedbackSystem/past_feedback.html', feedbacks=all_feedbacks)

@feedback_bp.route('/feedback/read/<int:feedback_id>')
@login_required
def read_feedback(feedback_id):
    feedback = feedback_service.get_feedback(feedback_id)
    if feedback and (feedback.recipient_id == current_user.id or feedback.sender_id == current_user.id):
        if (feedback.recipient_id == current_user.id):
            feedback_service.mark_feedback_as_read(feedback_id)
        return render_template('FeedbackSystem/read_feedback.html', feedback=feedback)
    else:
        flash("You don't have permission to read this feedback")
        return redirect(url_for('feedback.view_feedback'))
