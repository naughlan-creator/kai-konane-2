"""Messages between parents and teachers.

Two distinct reads that are easy to conflate: the **inbox** is unread received
messages only, the **history** is everything sent and received. Reading a
message moves it out of the first without removing it from the second.

Correspondent scoping (who may message whom, and about which learner) stays in
`web` for now, because it depends on the signed-in user. #8 moves it here once
the api knows who is calling.
"""
from flask import jsonify, request

from app.api import api_bp
from app.api.auth_seam import token_required
from app.api.authz import current_user_id, is_admin, require_owner
from app.api.serializers import feedback_out
from app.services.errors import Forbidden, NotFound, ValidationError
from app.services.feedback_service import FeedbackService

feedback_service = FeedbackService()


def _require_correspondent(message):
    """Only the two people on a message may read it."""
    if is_admin():
        return
    if current_user_id() not in (message.sender_id, message.recipient_id):
        raise Forbidden("That message is not yours")


@api_bp.post('/feedback')
@token_required
def send_feedback():
    """Body: {"sender_id", "recipient_id", "subject", "content", "child_id"?}."""
    payload = request.get_json(silent=True) or {}

    for field in ('sender_id', 'recipient_id'):
        if not isinstance(payload.get(field), int):
            raise ValidationError(f"{field} is required")

    subject = (payload.get('subject') or '').strip()
    content = (payload.get('content') or '').strip()
    if not subject or not content:
        raise ValidationError("A subject and a message are both required")

    # You may only send as yourself. Without this, any token could forge a
    # message from a head teacher to a parent.
    require_owner(payload['sender_id'], "You cannot send as another user")

    message = feedback_service.add_feedback(
        payload['sender_id'], payload['recipient_id'],
        subject, content, payload.get('child_id'))
    return jsonify(feedback=feedback_out(message)), 201


@api_bp.get('/feedback')
@token_required
def list_feedback():
    """`?recipient_id=&unread=true` for the inbox, `?participant_id=` for the
    full history. One of the two is required -- an unscoped listing would
    return everybody's mail.
    """
    recipient_id = request.args.get('recipient_id')
    participant_id = request.args.get('participant_id')
    unread = request.args.get('unread', '').lower() in ('1', 'true', 'yes')

    if participant_id:
        if not participant_id.isdigit():
            raise ValidationError("participant_id must be a number")
        require_owner(int(participant_id), "That is not your mail")
        messages = feedback_service.get_conversation(int(participant_id))
    elif recipient_id:
        if not recipient_id.isdigit():
            raise ValidationError("recipient_id must be a number")
        require_owner(int(recipient_id), "That is not your mail")
        if unread:
            messages = feedback_service.get_unread_feedbacks_by_recipient_id(
                int(recipient_id))
        else:
            messages = feedback_service.get_feedbacks_by_recipient_id(
                int(recipient_id))
    else:
        raise ValidationError("recipient_id or participant_id is required")

    return jsonify(feedback=[feedback_out(m) for m in messages])


@api_bp.get('/feedback/<int:feedback_id>')
@token_required
def get_feedback(feedback_id):
    message = feedback_service.get_feedback(feedback_id)
    if message is None:
        raise NotFound("No such message")
    _require_correspondent(message)
    return jsonify(feedback=feedback_out(message))


@api_bp.post('/feedback/<int:feedback_id>/read')
@token_required
def mark_read(feedback_id):
    """Separate from GET so reading is explicit.

    A GET that mutates would mean any preview, crawler or double-render marked
    mail as read.
    """
    existing = feedback_service.get_feedback(feedback_id)
    if existing is None:
        raise NotFound("No such message")
    _require_correspondent(existing)

    message = feedback_service.mark_feedback_as_read(feedback_id)
    if message is None:
        raise NotFound("No such message")
    return jsonify(feedback=feedback_out(message))
