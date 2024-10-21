from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import User, Role
from services.user_service import UserService
from services.parent_service import ParentService
from services.teacher_service import TeacherService
from config import db


profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile')
@login_required
def profile():
    if current_user.role == Role.PARENT:
        children = current_user.children
        return render_template('UserManagement/parent_profile.html', user=current_user, children=children)
    elif current_user.role == Role.TEACHER:
        return render_template('UserManagement/teacher_profile.html', user=current_user)
    else:
        return render_template('UserManagement/profile.html', user=current_user)

@profile_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_service = UserService(db)
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    result = user_service.update_user_profile(current_user.id, username, email, password)
    flash(result)

    if current_user.role == Role.PARENT:
        parent_service = ParentService(db)
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        education_level = request.form.get('education_level')
        result = parent_service.update_parent_profile(current_user.id, firstname, lastname, education_level)
        flash(result)
    elif current_user.role == Role.TEACHER:
        teacher_service = TeacherService(db)
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        result = teacher_service.update_teacher_profile(current_user.id, firstname, lastname)
        flash(result)

    return redirect(url_for('profile.profile'))

@profile_bp.route('/update_child_profile/<int:child_id>', methods=['POST'])
@login_required
def update_child_profile(child_id):
    if current_user.role != Role.PARENT:
        flash("You don't have permission to update child profiles")
        return redirect(url_for('profile.profile'))

    parent_service = ParentService(db)
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    age = request.form.get('age')
    gender = request.form.get('gender')
    race_ethnicity = request.form.get('race_ethnicity')
    lunch_type = request.form.get('lunch_type')

    result = parent_service.update_child_profile(child_id, firstname, lastname, age, gender, race_ethnicity, lunch_type)
    flash(result)
    return redirect(url_for('profile.profile'))