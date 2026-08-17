from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import app, db
from level_predictor import predict_child_level
from models.child import Child, Level, LunchType
from models.learning_plan import LearningPlan
from models.parent import EducationLevel, Parent
from models.teacher import Teacher
from models.user import Role, User
from routes.auth import admin_required, child_required, parent_required, teacher_required
from services.errors import ServiceError
from services.preschool_service import PreschoolService
from services.teacher_service import TeacherService
from services.user_service import UserService

user_bp = Blueprint('user', __name__, url_prefix='/users')


user_service = UserService(db)
preschool_service = PreschoolService(db)
teacher_service = TeacherService(db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user.login'

HOME_FOR_ROLE = {
    Role.TEACHER: 'user.teacher_home',
    Role.PARENT: 'user.parent_home',
    Role.ADMIN: 'user.admin_home',
    Role.CHILD: 'user.child_home',
}


@login_manager.user_loader
def load_user(user_id):
    # User is polymorphic, so a single lookup already returns the right
    # subclass. The old joinedload('*') is not valid in SQLAlchemy 2.x.
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@user_bp.route('/get/<int:id>', methods=['GET'])
@admin_required
def get_user(id):
    user = user_service.get_user(id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(_serialize_user(user))


@user_bp.route('/get', methods=['GET'])
@admin_required
def get_users():
    # Model instances are not JSON serialisable, so build plain dicts and never
    # include the password hash.
    return jsonify([_serialize_user(user) for user in user_service.get_users()])


def _serialize_user(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role.name if user.role else None,
        'type': user.type,
    }


@user_bp.route('/update/<int:id>', methods=['PUT'])
@admin_required
def update_user(id):
    # This is the shape the api will use for every endpoint on Day 2: let the
    # service raise, map the exception's status, and never string-match.
    payload = request.get_json(silent=True) or {}
    try:
        user = user_service.update_user(id, payload.get('username'), payload.get('email'))
    except ServiceError as e:
        return jsonify({'error': str(e)}), e.status
    return jsonify(_serialize_user(user)), 200


@user_bp.route('/delete/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    try:
        user_service.delete_user(id)
    except ServiceError as e:
        return jsonify({'error': str(e)}), e.status
    return jsonify({'status': 'deleted', 'id': id}), 200


@user_bp.route('/view_children')
@parent_required
def view_children():
    children = Child.query.filter_by(parent_id=current_user.id).all()
    return render_template('UserManagement/view_children.html', children=children)

@user_bp.route('/parent_home')
@parent_required
def parent_home():
    return render_template('UserManagement/parent_home.html')


@user_bp.route('/signup')
def signup():
    return render_template('UserManagement/signup.html')

@user_bp.route('/view_learners')
@teacher_required
def view_learners():
    learners = Child.query.filter_by(teacher_id=current_user.id).all()
    return render_template('UserManagement/view_learners.html', learners=learners)

@user_bp.route('/home')
@login_required
def home():
    endpoint = HOME_FOR_ROLE.get(current_user.role)
    if endpoint:
        return redirect(url_for(endpoint))
    flash("Invalid user role", "error")
    return redirect(url_for('user.logout'))

@user_bp.route('/parent_signup_1', methods=['GET', 'POST'])
def parent_signup_1():
    if request.method == 'POST':
        kids = request.form.get('kids')
        if kids and kids.isdigit() and 0 < int(kids) <= 20:
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

        if user_service.get_user_by_username(username):
            return render_template('UserManagement/parent_signup_2.html',
                                   notification="Username already exists. Please choose a different username.")

        if User.query.filter_by(email=email).first():
            return render_template('UserManagement/parent_signup_2.html',
                                   notification="That email address is already registered.")

        parent_data = session.get('parent_data', {})
        parent_data.update({
            'username': username,
            'email': email,
            'password': password
        })
        session['parent_data'] = parent_data

        return redirect(url_for('user.parent_signup_3'))

    return render_template('UserManagement/parent_signup_2.html')

@user_bp.route('/parent_signup_3', methods=['GET', 'POST'])
def parent_signup_3():
    if 'parent_data' not in session or 'kids' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.parent_signup_1'))

    if request.method == 'POST':
        education_level = EducationLevel.coerce(request.form.get('education_level'))
        if education_level is None:
            return render_template('UserManagement/parent_signup_3.html',
                                   preschools=preschool_service.get_preschools(),
                                   EducationLevel=EducationLevel,
                                   notification="Please select an education level.")

        parent_data = session.get('parent_data', {})
        parent_data.update({
            'firstname': request.form.get('firstname'),
            'lastname': request.form.get('lastname'),
            'education_level': education_level.name,
            'preschool_id': _as_int(request.form.get('preschool_id'))
        })
        session['parent_data'] = parent_data
        return redirect(url_for('user.parent_signup_4'))

    preschools = preschool_service.get_preschools()
    return render_template('UserManagement/parent_signup_3.html', preschools=preschools, EducationLevel=EducationLevel)

@user_bp.route('/parent_signup_4', methods=['GET', 'POST'])
def parent_signup_4():
    if 'parent_data' not in session or 'kids' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.parent_signup_1'))

    kids = session['kids']
    parent_data = session.get('parent_data', {})
    teachers = teacher_service.get_teachers()

    if request.method == 'POST':
        error = None
        try:
            education_level = EducationLevel.coerce(parent_data.get('education_level'))
            if education_level is None:
                raise ValueError("Missing education level")

            # Create parent
            parent = Parent(
                firstname=parent_data.get('firstname'),
                lastname=parent_data.get('lastname'),
                username=parent_data.get('username'),
                password=generate_password_hash(parent_data.get('password')),
                email=parent_data.get('email'),
                role=Role.PARENT,
                education_level=education_level
            )
            db.session.add(parent)
            db.session.flush()

            success_log = []
            seen_usernames = set()

            for i in range(1, kids + 1):
                child_username = (request.form.get(f'child_username_{i}') or '').strip()
                child_age = _as_int(request.form.get(f'child_age_{i}'))
                teacher_id = _as_int(request.form.get(f'child_teacher_{i}'))
                lunch_type = LunchType.coerce(request.form.get(f'child_lunch_{i}'))

                if not child_username or child_age is None or lunch_type is None:
                    raise ValueError(f"Incomplete details for child {i}")
                if child_username in seen_usernames:
                    raise ValueError(f"Duplicate username '{child_username}' in this form")
                if User.query.filter_by(username=child_username).first():
                    raise ValueError(f"Username '{child_username}' is already taken")
                seen_usernames.add(child_username)

                child = Child(
                    firstname=request.form.get(f'child_name_{i}'),
                    lastname=parent.lastname,
                    age=child_age,
                    gender=request.form.get(f'child_gender_{i}'),
                    parent_id=parent.id,
                    teacher_id=teacher_id,
                    preschool_id=_as_int(parent_data.get('preschool_id')),
                    username=child_username,
                    password=generate_password_hash(request.form.get(f'child_password_{i}')),
                    email=f"{child_username}@kaikonane.local",
                    role=Role.CHILD,
                    race_ethnicity=request.form.get(f'child_race_{i}'),
                    lunch_type=lunch_type,
                    parent_education=parent.education_level
                )
                db.session.add(child)
                db.session.flush()
                success_log.append(f"Created child: {child.firstname}")

                # predict_child_level returns a Level. The old code mapped an
                # integer through {0: BEGINNER, ...}, which never matched, so
                # every child silently started as a beginner.
                recommended_level = predict_child_level(child.id) or Level.BEGINNER
                child.recommended_level = recommended_level

                db.session.add(LearningPlan(
                    child_id=child.id,
                    science_level=recommended_level,
                    technology_level=recommended_level,
                    engineering_level=recommended_level,
                    math_level=recommended_level,
                    story_level=recommended_level
                ))
                db.session.flush()
                success_log.append(f"Created learning plan for: {child.firstname}")

            db.session.commit()
            current_app.logger.info(f"Registration successful: {'; '.join(success_log)}")

            session.clear()
            flash("Registration successful! Learning plans created for all children.", "success")
            return redirect(url_for('user.login'))

        except ValueError as e:
            db.session.rollback()
            error = str(e)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {str(e)}")
            error = "Registration failed. Please try again."

        return render_template('UserManagement/parent_signup_4.html',
                               kids=kids,
                               teachers=teachers,
                               LunchType=LunchType,
                               notification=error,
                               error=error)

    return render_template('UserManagement/parent_signup_4.html',
                         kids=kids,
                         teachers=teachers,
                         LunchType=LunchType)

@user_bp.route('/teacher_signup_1', methods=['GET', 'POST'])
def teacher_signup_1():
    preschools = preschool_service.get_preschools()

    if request.method == 'POST':
        preschool_id = _as_int(request.form.get('preschool_id'))
        if preschool_id and preschool_service.get_preschool(preschool_id):
            session['preschool_id'] = preschool_id
            return redirect(url_for('user.teacher_signup_2'))
        # 'preschools' used to be referenced here before it was assigned.
        return render_template('UserManagement/teacher_signup_1.html',
                               preschools=preschools,
                               notification="Please select a preschool.")

    return render_template('UserManagement/teacher_signup_1.html', preschools=preschools)


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
        if User.query.filter_by(username=username).first():
            return render_template('UserManagement/teacher_signup_2.html',
                                   notification="Username already exists. Please choose a different username.")
        if User.query.filter_by(email=email).first():
            return render_template('UserManagement/teacher_signup_2.html',
                                   notification="That email address is already registered.")

        session['teacher_data'] = {
            'username': username,
            'email': email,
            'password': password
        }

        return redirect(url_for('user.teacher_signup_3'))
    return render_template('UserManagement/teacher_signup_2.html')


@user_bp.route('/teacher_signup_3', methods=['GET', 'POST'])
def teacher_signup_3():
    if 'teacher_data' not in session:
        flash("Please start from the beginning.", "warning")
        return redirect(url_for('user.teacher_signup_1'))

    if request.method == 'POST':
        teacher_data = session.get('teacher_data', {})
        preschool_id = session.get('preschool_id')

        teacher = Teacher(
            username=teacher_data['username'],
            password=generate_password_hash(teacher_data['password']),
            email=teacher_data['email'],
            role=Role.TEACHER,
            firstname=request.form.get('firstname'),
            lastname=request.form.get('lastname'),
            preschool_id=preschool_id
        )
        db.session.add(teacher)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Teacher signup error: {e}")
            return render_template('UserManagement/teacher_signup_3.html',
                                   notification="Signup failed. Please try again.")

        session.pop('teacher_data', None)
        session.pop('preschool_id', None)

        flash("Teacher signup successful!", "success")
        return redirect(url_for('user.login'))
    return render_template('UserManagement/teacher_signup_3.html')

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # User is polymorphic; one query returns the Parent/Teacher/Child row.
        user = User.query.filter_by(username=username).first()

        if user and user.password and password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('user.home'))

        return render_template('UserManagement/login.html',
                               notification="Invalid username or password")

    return render_template('UserManagement/login.html')

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('user.login'))

@user_bp.route('/child_home')
@child_required
def child_home():
    user = db.session.get(Child, current_user.id)
    if user is None:
        flash("Your learner profile is incomplete. Please contact your teacher.", "error")
        return redirect(url_for('user.logout'))
    return render_template('UserManagement/child_home.html', user=user)

@user_bp.route('/teacher_home')
@teacher_required
def teacher_home():
    return render_template('UserManagement/teacher_home.html')

@user_bp.route('/admin_home')
@admin_required
def admin_home():
    return render_template('UserManagement/admin_home.html')
