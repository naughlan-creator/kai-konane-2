from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.config import db
from app.models.child import EducationLevel, LunchType
from app.models.user import Role
from app.routes.auth import parent_required
from app.services.errors import ServiceError
from app.services.parent_service import ParentService
from app.services.teacher_service import TeacherService
from app.services.user_service import UserService

profile_bp = Blueprint('profile', __name__)

user_service = UserService(db)
parent_service = ParentService(db)
teacher_service = TeacherService(db)


@profile_bp.route('/profile')
@login_required
def profile():
    if current_user.role == Role.PARENT:
        return render_template('UserManagement/parent_profile.html',
                               user=current_user,
                               children=current_user.children,
                               EducationLevel=EducationLevel,
                               LunchType=LunchType)
    if current_user.role == Role.TEACHER:
        return render_template('UserManagement/teacher_profile.html', user=current_user)
    # UserManagement/profile.html did not exist, so admins and children got a
    # TemplateNotFound instead of a profile page.
    return render_template('UserManagement/profile.html', user=current_user)


@profile_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        user_service.update_user_profile(
            current_user.id,
            request.form.get('username'),
            request.form.get('email'),
            request.form.get('password'),
        )

        if current_user.role == Role.PARENT:
            parent_service.update_parent_profile(
                current_user.id,
                request.form.get('firstname'),
                request.form.get('lastname'),
                request.form.get('education_level'),
            )
        elif current_user.role == Role.TEACHER:
            teacher_service.update_teacher_profile(
                current_user.id,
                request.form.get('firstname'),
                request.form.get('lastname'),
            )
    except ServiceError as e:
        flash(str(e), 'error')
        return redirect(url_for('profile.profile'))

    flash('Profile updated', 'success')
    return redirect(url_for('profile.profile'))


@profile_bp.route('/update_child_profile/<int:child_id>', methods=['POST'])
@parent_required
def update_child_profile(child_id):
    # A parent may only edit their own children.
    if child_id not in {child.id for child in current_user.children}:
        flash("You can only update your own children's profiles", 'error')
        return redirect(url_for('profile.profile'))

    try:
        child = parent_service.update_child_profile(
            child_id,
            request.form.get('firstname'),
            request.form.get('lastname'),
            request.form.get('age'),
            request.form.get('gender'),
            request.form.get('race_ethnicity'),
            request.form.get('lunch_type'),
        )
    except ServiceError as e:
        flash(str(e), 'error')
        return redirect(url_for('profile.profile'))

    flash(f"Updated {child.firstname}'s profile", 'success')
    return redirect(url_for('profile.profile'))
