from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.user import Role
from app.routes.auth import roles_required
from app.services.feedback_service import FeedbackService

feedback_bp = Blueprint('feedback', __name__, url_prefix='/feedbacks')

feedback_service = FeedbackService()

# Only parents and teachers exchange feedback.
correspondent_required = roles_required(Role.PARENT, Role.TEACHER)


def _correspondents_for(user):
    """Who this user may exchange feedback with, and about whom"""
    pairs = {}
    if user.role == Role.PARENT:
        for child in user.children:
            if child.teacher:
                pairs.setdefault(child.teacher, []).append(child)
    elif user.role == Role.TEACHER:
        for child in user.students:
            if child.parent:
                pairs.setdefault(child.parent, []).append(child)
    return [{'person': person, 'shared_children': kids}
            for person, kids in pairs.items()]


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
    correspondents = _correspondents_for(current_user)
    if recipient_id:
        allowed = {c['person'].id for c in correspondents}
        if not str(recipient_id).isdigit() or int(recipient_id) not in allowed:
            flash("You can only message your child's teacher.", "error")
            return redirect(url_for('feedback.write_feedback'))
        shared = next(c['shared_children'] for c in correspondents
                      if c['person'].id == int(recipient_id))
        return render_template('FeedbackSystem/write_feedback.html',
                               recipient_id=recipient_id, children=shared)

    return render_template('FeedbackSystem/select_feedback_receiver.html',
                           recipients=correspondents)

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

    correspondents = _correspondents_for(current_user)
    allowed = {c['person'].id for c in correspondents}
    if not str(recipient_id).isdigit() or int(recipient_id) not in allowed:
        flash("That recipient is not available to you", "error")
        return redirect(url_for('feedback.write_feedback'))
    recipient_id = int(recipient_id)

    shared = next(c['shared_children'] for c in correspondents
                  if c['person'].id == recipient_id)
    if child_id is not None:
        allowed_children = {child.id for child in shared}
        if not child_id.isdigit() or int(child_id) not in allowed_children:
            flash("You can only send feedback about a shared learner", "error")
            return redirect(url_for('feedback.write_feedback', recipient_id=recipient_id))
        child_id = int(child_id)

    feedback_service.add_feedback(current_user.id, recipient_id, subject, content, child_id)
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
    feedbacks = feedback_service.get_conversation(current_user.id)
    return render_template('FeedbackSystem/past_feedback.html', feedbacks=feedbacks)

@feedback_bp.route('/feedback/read/<int:feedback_id>')
@correspondent_required
def read_feedback(feedback_id):
    feedback = feedback_service.get_feedback(feedback_id)
    if feedback and (feedback.recipient_id == current_user.id or feedback.sender_id == current_user.id):
        if feedback.recipient_id == current_user.id:
            feedback_service.mark_feedback_as_read(feedback_id)
        return render_template('FeedbackSystem/read_feedback.html', feedback=feedback)

    flash("You don't have permission to read this feedback")
    return redirect(url_for('feedback.feedback_home'))
