"""Accounts: login, logout, the role home pages, and the two signup wizards.

The wizards are the clearest example of the split. Steps 1-3 accumulate form
state in the session and write nothing; the final step posts the whole family to
`POST /parents` in a single call, and the api creates the parent, every child and
every learning plan in one transaction. `web` never sees a password hash and
never runs the level predictor.
"""
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app import api_client
from app.identity import sign_in, sign_out
from app.roles import Role
from app.routes.auth import (
    admin_required,
    child_required,
    parent_required,
    teacher_required,
)

user_bp = Blueprint('user', __name__, url_prefix='/users')

HOME_FOR_ROLE = {
    Role.TEACHER: 'user.teacher_home',
    Role.PARENT: 'user.parent_home',
    Role.ADMIN: 'user.admin_home',
    Role.CHILD: 'user.child_home',
}

MAX_KIDS = 20


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _preschools():
    try:
        return api_client.get('preschools')['preschools']
    except api_client.ApiError:
        return []


def _teachers():
    try:
        return api_client.get('teachers')['teachers']
    except api_client.ApiError:
        return []


def _enum(name):
    try:
        return api_client.get('enums')[name]
    except api_client.ApiError:
        return []


def _taken(username=None, email=None):
    """Ask the api whether a name is free.

    Advisory only: someone can take it between here and the final write, which
    is why the api re-checks inside the transaction and returns 409. This exists
    so a four-screen wizard can fail on screen two instead of screen four.
    """
    try:
        return api_client.get('users/availability',
                              params={'username': username or '',
                                      'email': email or ''})
    except api_client.ApiError:
        return {'username_taken': False, 'email_taken': False}


# --------------------------------------------------------------- sessions

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        try:
            result = api_client.post('auth/login', json={
                'username': request.form.get('username'),
                'password': request.form.get('password'),
            })
        except api_client.ApiUnauthorized:
            # The api's message is deliberately vague; do not improve on it.
            flash('Invalid username or password', 'error')
            return render_template('UserManagement/login.html'), 401
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('UserManagement/login.html'), 503

        login_user(sign_in(result['user'], result['token']))
        return redirect(request.args.get('next') or url_for('user.home'))

    return render_template('UserManagement/login.html')


@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    sign_out()
    flash('You have been logged out', 'info')
    return redirect(url_for('user.login'))


@user_bp.route('/home')
@login_required
def home():
    endpoint = HOME_FOR_ROLE.get(current_user.role)
    if endpoint:
        return redirect(url_for(endpoint))
    flash("Invalid user role", "error")
    return redirect(url_for('user.logout'))


# ------------------------------------------------------------ home pages

@user_bp.route('/parent_home')
@parent_required
def parent_home():
    return render_template('UserManagement/parent_home.html')


@user_bp.route('/teacher_home')
@teacher_required
def teacher_home():
    return render_template('UserManagement/teacher_home.html')


@user_bp.route('/admin_home')
@admin_required
def admin_home():
    return render_template('UserManagement/admin_home.html')


@user_bp.route('/child_home')
@child_required
def child_home():
    try:
        user = api_client.get(f'children/{current_user.id}')['child']
    except api_client.ApiNotFound:
        flash("Your learner profile is incomplete. Please contact your teacher.",
              "error")
        return redirect(url_for('user.logout'))
    return render_template('UserManagement/child_home.html', user=user)


@user_bp.route('/view_children')
@parent_required
def view_children():
    children = api_client.get('children',
                              params={'parent_id': current_user.id})['children']
    return render_template('UserManagement/view_children.html', children=children)


@user_bp.route('/view_learners')
@teacher_required
def view_learners():
    learners = api_client.get('children',
                              params={'teacher_id': current_user.id})['children']
    return render_template('UserManagement/view_learners.html', learners=learners)


@user_bp.route('/signup')
def signup():
    return render_template('UserManagement/signup.html')


# ------------------------------------------------------ parent signup wizard

@user_bp.route('/parent_signup_1', methods=['GET', 'POST'])
def parent_signup_1():
    if request.method == 'POST':
        kids = request.form.get('kids')
        if kids and kids.isdigit() and 0 < int(kids) <= MAX_KIDS:
            session['kids'] = int(kids)
            return redirect(url_for('user.parent_signup_2'))
        return render_template('UserManagement/parent_signup_1.html',
                               notification="Please enter a valid number of kids.")
    return render_template('UserManagement/parent_signup_1.html')


@user_bp.route('/parent_signup_2', methods=['GET', 'POST'])
def parent_signup_2():
    if 'kids' not in session:
        # redirect() takes no notification argument -- this used to raise a
        # TypeError instead of sending the visitor back to step 1.
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.parent_signup_1'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password')

        if not username or not email or not password:
            return render_template('UserManagement/parent_signup_2.html',
                                   notification="Please fill in every field.")

        availability = _taken(username, email)
        if availability['username_taken']:
            return render_template(
                'UserManagement/parent_signup_2.html',
                notification="Username already exists. Please choose a different username.")
        if availability['email_taken']:
            return render_template(
                'UserManagement/parent_signup_2.html',
                notification="That email address is already registered.")

        parent_data = session.get('parent_data', {})
        parent_data.update({'username': username, 'email': email,
                            'password': password})
        session['parent_data'] = parent_data

        return redirect(url_for('user.parent_signup_3'))

    return render_template('UserManagement/parent_signup_2.html')


@user_bp.route('/parent_signup_3', methods=['GET', 'POST'])
def parent_signup_3():
    if 'parent_data' not in session or 'kids' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.parent_signup_1'))

    education_levels = _enum('EducationLevel')

    if request.method == 'POST':
        education_level = request.form.get('education_level')
        if not education_level or education_level not in {
                level['name'] for level in education_levels}:
            return render_template('UserManagement/parent_signup_3.html',
                                   preschools=_preschools(),
                                   EducationLevel=education_levels,
                                   notification="Please select an education level.")

        parent_data = session.get('parent_data', {})
        parent_data.update({
            'firstname': request.form.get('firstname'),
            'lastname': request.form.get('lastname'),
            'education_level': education_level,
            'preschool_id': _as_int(request.form.get('preschool_id')),
        })
        session['parent_data'] = parent_data
        return redirect(url_for('user.parent_signup_4'))

    return render_template('UserManagement/parent_signup_3.html',
                           preschools=_preschools(),
                           EducationLevel=education_levels)


@user_bp.route('/parent_signup_4', methods=['GET', 'POST'])
def parent_signup_4():
    if 'parent_data' not in session or 'kids' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.parent_signup_1'))

    kids = session['kids']
    parent_data = session.get('parent_data', {})
    teachers = _teachers()
    lunch_types = _enum('LunchType')

    if request.method == 'POST':
        children = []
        for i in range(1, kids + 1):
            children.append({
                'username': (request.form.get(f'child_username_{i}') or '').strip(),
                'password': request.form.get(f'child_password_{i}'),
                'firstname': request.form.get(f'child_name_{i}'),
                'age': request.form.get(f'child_age_{i}'),
                'gender': request.form.get(f'child_gender_{i}'),
                'race_ethnicity': request.form.get(f'child_race_{i}'),
                'lunch_type': request.form.get(f'child_lunch_{i}'),
                'teacher_id': _as_int(request.form.get(f'child_teacher_{i}')),
            })

        try:
            # One call, one transaction. The api creates the parent, every
            # child and every learning plan together, or none of them -- a
            # child with no plan can see no content at all.
            api_client.post('parents', json={
                'username': parent_data.get('username'),
                'email': parent_data.get('email'),
                'password': parent_data.get('password'),
                'firstname': parent_data.get('firstname'),
                'lastname': parent_data.get('lastname'),
                'education_level': parent_data.get('education_level'),
                'preschool_id': parent_data.get('preschool_id'),
                'children': children,
            })
        except api_client.ApiError as e:
            current_app.logger.info("Registration rejected: %s", e.message)
            return render_template('UserManagement/parent_signup_4.html',
                                   kids=kids, teachers=teachers,
                                   LunchType=lunch_types,
                                   notification=e.message, error=e.message)

        session.clear()
        flash("Registration successful! Learning plans created for all children.",
              "success")
        return redirect(url_for('user.login'))

    return render_template('UserManagement/parent_signup_4.html',
                           kids=kids, teachers=teachers,
                           LunchType=lunch_types)


# ----------------------------------------------------- teacher signup wizard

@user_bp.route('/teacher_signup_1', methods=['GET', 'POST'])
def teacher_signup_1():
    preschools = _preschools()

    if request.method == 'POST':
        preschool_id = _as_int(request.form.get('preschool_id'))
        if preschool_id and any(p['id'] == preschool_id for p in preschools):
            session['preschool_id'] = preschool_id
            return redirect(url_for('user.teacher_signup_2'))
        # 'preschools' used to be referenced here before it was assigned.
        return render_template('UserManagement/teacher_signup_1.html',
                               preschools=preschools,
                               notification="Please select a preschool.")

    return render_template('UserManagement/teacher_signup_1.html',
                           preschools=preschools)


@user_bp.route('/teacher_signup_2', methods=['GET', 'POST'])
def teacher_signup_2():
    if 'preschool_id' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.teacher_signup_1'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password')

        if not username or not email or not password:
            return render_template('UserManagement/teacher_signup_2.html',
                                   notification="Please fill in every field.")

        availability = _taken(username, email)
        if availability['username_taken']:
            return render_template(
                'UserManagement/teacher_signup_2.html',
                notification="Username already exists. Please choose a different username.")
        if availability['email_taken']:
            return render_template(
                'UserManagement/teacher_signup_2.html',
                notification="That email address is already registered.")

        session['teacher_data'] = {'username': username, 'email': email,
                                   'password': password}
        return redirect(url_for('user.teacher_signup_3'))

    return render_template('UserManagement/teacher_signup_2.html')


@user_bp.route('/teacher_signup_3', methods=['GET', 'POST'])
def teacher_signup_3():
    if 'teacher_data' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.teacher_signup_1'))

    if request.method == 'POST':
        teacher_data = session.get('teacher_data', {})
        try:
            api_client.post('teachers', json={
                'username': teacher_data.get('username'),
                'email': teacher_data.get('email'),
                'password': teacher_data.get('password'),
                'firstname': request.form.get('firstname'),
                'lastname': request.form.get('lastname'),
                'preschool_id': session.get('preschool_id'),
            })
        except api_client.ApiError as e:
            current_app.logger.info("Teacher signup rejected: %s", e.message)
            return render_template('UserManagement/teacher_signup_3.html',
                                   notification=e.message)

        session.pop('teacher_data', None)
        session.pop('preschool_id', None)

        flash("Teacher signup successful!", "success")
        return redirect(url_for('user.login'))

    return render_template('UserManagement/teacher_signup_3.html')
