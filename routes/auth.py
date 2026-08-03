"""Shared authorisation helpers for the blueprints."""
from functools import wraps

from flask import flash, redirect, url_for, jsonify, request
from flask_login import current_user

from models.user import Role


def roles_required(*roles):
    """Allow the view only for the given roles.

    ``@login_required`` on its own answers "is anyone signed in?", not "is this
    the right kind of user?" -- several admin views used to be reachable by any
    logged-in child.

    Note the decorator order: this must sit *below* ``@blueprint.route`` so the
    route registers the wrapped function.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('user.login', next=request.path))
            if current_user.role not in roles:
                if request.accept_mimetypes.best == 'application/json':
                    return jsonify({'error': 'Unauthorized'}), 403
                flash("You don't have permission to view that page", "error")
                return redirect(url_for('user.home'))
            return view(*args, **kwargs)
        return wrapper
    return decorator


admin_required = roles_required(Role.ADMIN)
teacher_required = roles_required(Role.TEACHER)
parent_required = roles_required(Role.PARENT)
child_required = roles_required(Role.CHILD)
