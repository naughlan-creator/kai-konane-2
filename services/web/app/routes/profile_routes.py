"""Profile viewing and editing."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import api_client
from app.roles import Role
from app.routes.auth import parent_required

profile_bp = Blueprint('profile', __name__)

# The dropdowns used to be built from the model enums. web has no models, so it
# asks the api for the same lists -- see GET /enums.
ENUM_FALLBACK = {'EducationLevel': [], 'LunchType': []}


def _enums():
    try:
        return api_client.get('enums')
    except api_client.ApiError:
        return ENUM_FALLBACK


@profile_bp.route('/profile')
@login_required
def profile():
    enums = _enums()
    if current_user.role == Role.PARENT:
        children = api_client.get(
            'children', params={'parent_id': current_user.id})['children']
        return render_template('UserManagement/parent_profile.html',
                               user=current_user,
                               children=children,
                               EducationLevel=enums.get('EducationLevel', []),
                               LunchType=enums.get('LunchType', []))
    if current_user.role == Role.TEACHER:
        return render_template('UserManagement/teacher_profile.html',
                               user=current_user)
    # UserManagement/profile.html did not exist, so admins and children got a
    # TemplateNotFound instead of a profile page.
    return render_template('UserManagement/profile.html', user=current_user)


@profile_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        api_client.patch(f'users/{current_user.id}', json={
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
        })

        if current_user.role == Role.PARENT:
            api_client.patch(f'parents/{current_user.id}', json={
                'firstname': request.form.get('firstname'),
                'lastname': request.form.get('lastname'),
                'education_level': request.form.get('education_level'),
            })
        elif current_user.role == Role.TEACHER:
            api_client.patch(f'teachers/{current_user.id}', json={
                'firstname': request.form.get('firstname'),
                'lastname': request.form.get('lastname'),
            })
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('profile.profile'))

    flash('Profile updated', 'success')
    return redirect(url_for('profile.profile'))


@profile_bp.route('/update_child_profile/<int:child_id>', methods=['POST'])
@parent_required
def update_child_profile(child_id):
    # A parent may only edit their own children. The check stays here as well as
    # in the api: this one produces a flash and a redirect, which is what a form
    # post needs.
    owned = {child['id'] for child in api_client.get(
        'children', params={'parent_id': current_user.id})['children']}
    if child_id not in owned:
        flash("You can only update your own children's profiles", 'error')
        return redirect(url_for('profile.profile'))

    try:
        child = api_client.patch(f'children/{child_id}', json={
            'firstname': request.form.get('firstname'),
            'lastname': request.form.get('lastname'),
            'age': request.form.get('age'),
            'gender': request.form.get('gender'),
            'race_ethnicity': request.form.get('race_ethnicity'),
            'lunch_type': request.form.get('lunch_type'),
        })['child']
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('profile.profile'))

    flash(f"Updated {child['firstname']}'s profile", 'success')
    return redirect(url_for('profile.profile'))
