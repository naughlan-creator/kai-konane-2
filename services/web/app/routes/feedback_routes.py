"""Messages between parents and teachers.

Correspondent scoping stays here rather than in the api because it is a
presentation concern -- who appears in the picker -- and because the checks
produce flashes and redirects, which only a form flow needs. The api still
validates ids independently.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import api_client
from app.roles import Role
from app.routes.auth import roles_required

feedback_bp = Blueprint('feedback', __name__, url_prefix='/feedbacks')

# Only parents and teachers exchange feedback.
correspondent_required = roles_required(Role.PARENT, Role.TEACHER)


def _correspondents_for(user):
    """Who this user may exchange feedback with, and about whom.

    A parent may write to each of their children's teachers, about the children
    they share. A teacher may write to each learner's parent. Anyone else is not
    a correspondent -- which is what stops a teacher seeing every parent in the
    school, and stops a parent seeing another family's child.
    """
    pairs = {}
    if user.role == Role.PARENT:
        children = api_client.get(
            'children', params={'parent_id': user.id})['children']
        key = 'teacher_id'
    elif user.role == Role.TEACHER:
        children = api_client.get(
            'children', params={'teacher_id': user.id})['children']
        key = 'parent_id'
    else:
        return []

    for child in children:
        other_id = child.get(key)
        if other_id:
            pairs.setdefault(other_id, []).append(child)

    correspondents = []
    for person_id, kids in pairs.items():
        try:
            person = api_client.get(f'users/{person_id}')['user']
        except api_client.ApiError:
            # A teacher who has since been removed should not break the picker.
            continue
        correspondents.append({'person': person, 'shared_children': kids})
    return correspondents


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
        allowed = {c['person']['id'] for c in correspondents}
        if not str(recipient_id).isdigit() or int(recipient_id) not in allowed:
            flash("You can only message your child's teacher.", "error")
            return redirect(url_for('feedback.write_feedback'))
        shared = next(c['shared_children'] for c in correspondents
                      if c['person']['id'] == int(recipient_id))
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
        return redirect(url_for('feedback.write_feedback',
                                recipient_id=recipient_id))

    correspondents = _correspondents_for(current_user)
    allowed = {c['person']['id'] for c in correspondents}
    if not str(recipient_id).isdigit() or int(recipient_id) not in allowed:
        flash("That recipient is not available to you", "error")
        return redirect(url_for('feedback.write_feedback'))
    recipient_id = int(recipient_id)

    shared = next(c['shared_children'] for c in correspondents
                  if c['person']['id'] == recipient_id)
    if child_id is not None:
        allowed_children = {child['id'] for child in shared}
        if not child_id.isdigit() or int(child_id) not in allowed_children:
            flash("You can only send feedback about a shared learner", "error")
            return redirect(url_for('feedback.write_feedback',
                                    recipient_id=recipient_id))
        child_id = int(child_id)

    try:
        api_client.post('feedback', json={
            'sender_id': current_user.id,
            'recipient_id': recipient_id,
            'subject': subject,
            'content': content,
            'child_id': child_id,
        })
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('feedback.write_feedback',
                                recipient_id=recipient_id))

    flash("Feedback sent successfully")
    return redirect(url_for('feedback.feedback_home'))


@feedback_bp.route('/feedback/view')
@correspondent_required
def view_feedback():
    # The inbox: only what has not been read yet.
    feedbacks = api_client.get('feedback', params={
        'recipient_id': current_user.id, 'unread': 'true'})['feedback']
    return render_template('FeedbackSystem/view_feedback.html',
                           feedbacks=feedbacks)


@feedback_bp.route('/feedback/past')
@correspondent_required
def past_feedback():
    feedbacks = api_client.get(
        'feedback', params={'participant_id': current_user.id})['feedback']
    return render_template('FeedbackSystem/past_feedback.html',
                           feedbacks=feedbacks)


@feedback_bp.route('/feedback/read/<int:feedback_id>')
@correspondent_required
def read_feedback(feedback_id):
    try:
        feedback = api_client.get(f'feedback/{feedback_id}')['feedback']
    except api_client.ApiError:
        feedback = None

    if feedback and current_user.id in (feedback['recipient_id'],
                                        feedback['sender_id']):
        if feedback['recipient_id'] == current_user.id:
            # Marking read is a POST on the api so that a preview or a crawler
            # cannot empty someone's inbox by following links.
            feedback = api_client.post(
                f'feedback/{feedback_id}/read')['feedback']
        return render_template('FeedbackSystem/read_feedback.html',
                               feedback=feedback)

    flash("You don't have permission to read this feedback")
    return redirect(url_for('feedback.feedback_home'))
