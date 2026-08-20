"""Who may touch what.

`token_required` answers "who is calling?". This module answers "may they do
this to that?" -- and until it existed, nothing did: a parent's token could
PATCH an administrator's password and then sign in as them.

Two rules shape everything here:

* **Deny by default.** An unrecognised role gets nothing. The predecessor of
  this module compared `role.name` to a lowercase string, never matched, and so
  allowed everyone -- a check that fails open is worse than no check, because it
  reads like protection.
* **Identity comes from the token, never the request.** A body or query string
  saying `parent_id=3` is a claim by the caller; `g.current_user_id` is a claim
  the api signed. Only the second is evidence.
"""
from flask import g

from app.models.child import Child
from app.services.errors import Forbidden


def current_user_id():
    return getattr(g, 'current_user_id', None)


def current_role():
    return getattr(g, 'current_role', None)


def is_admin():
    return current_role() == 'ADMIN'


def require_admin():
    if not is_admin():
        raise Forbidden("That is an administrator action")


def require_self_or_admin(user_id):
    """The account owner, or an administrator.

    Used for anything that edits an account: a user may change their own
    details, an admin may change anyone's, and nobody else may touch either.
    """
    if is_admin():
        return
    if current_user_id() != user_id:
        raise Forbidden("That is not your account")


def child_or_403(child_id, child_service):
    """Fetch a child the caller is entitled to see, or refuse.

    A parent may see their own children, a teacher their own learners, a child
    only themselves, an admin anyone. Returns the Child so callers do not fetch
    it twice.
    """
    child = child_service.get_child(child_id)
    if child is None:
        return None

    role = current_role()
    viewer = current_user_id()

    if role == 'ADMIN':
        allowed = True
    elif role == 'PARENT':
        allowed = child.parent_id == viewer
    elif role == 'TEACHER':
        allowed = child.teacher_id == viewer
    elif role == 'CHILD':
        allowed = child.id == viewer
    else:
        allowed = False

    if not allowed:
        raise Forbidden("That is not your learner")
    return child


def require_child_access(child_id, child_service):
    """As above, but for endpoints that only need the permission check."""
    return child_or_403(child_id, child_service)


def shares_a_child_with(other_user_id):
    """Whether the caller and another user are connected by a learner.

    This is what lets a parent read the teacher's name in a message thread
    without opening every account in the school to every account in the school.
    """
    viewer = current_user_id()
    role = current_role()

    if role == 'PARENT':
        return Child.query.filter_by(parent_id=viewer,
                                     teacher_id=other_user_id).first() is not None
    if role == 'TEACHER':
        return Child.query.filter_by(teacher_id=viewer,
                                     parent_id=other_user_id).first() is not None
    return False


def require_visible_user(user_id):
    """May the caller read this account?

    Self, an administrator, a correspondent they share a learner with, or one of
    their own children. Anything else is refused -- an id is trivially guessable,
    so "authenticated" cannot mean "may read every user record".
    """
    if is_admin() or current_user_id() == user_id:
        return
    if shares_a_child_with(user_id):
        return

    # A parent or teacher reading one of their own learners.
    child = Child.query.filter_by(id=user_id).first()
    if child is not None:
        role = current_role()
        if role == 'PARENT' and child.parent_id == current_user_id():
            return
        if role == 'TEACHER' and child.teacher_id == current_user_id():
            return

    raise Forbidden("You cannot view that account")


def require_owner(owner_id, message="That is not yours"):
    """The caller must be the named owner, or an administrator."""
    if is_admin():
        return
    if current_user_id() != owner_id:
        raise Forbidden(message)
