from flask import session, Blueprint, request, jsonify, flash, render_template, redirect, url_for, current_app
from services.user_service import UserService
from services.preschool_service import PreschoolService
from services.teacher_service import TeacherService
from services.learning_plan_service import LearningPlanService
from models.user import User, Role
from models.parent import Parent, EducationLevel
from models.teacher import Teacher
from models.child import Child, Level, LunchType
from models.learning_plan import LearningPlan
from level_predictor import predict_child_level
from flask_login import login_user, logout_user, login_required, LoginManager, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from config import app, db


user_bp = Blueprint('user', __name__, url_prefix='/users')


user_service = UserService(db)
preschool_service = PreschoolService(db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user.login'

@login_manager.user_loader
def load_user(user_id):
    for UserModel in [User, Parent, Teacher, Child]:
        user = UserModel.query.get(int(user_id))
        if user:
            return user
    return None
@user_bp.route('/add', methods=['POST'])
def add_user():
    user = request.json
    result = user_service.add_user(user)
    return jsonify(result), 201

@user_bp.route('/get/<int:id>', methods=['GET'])
def get_user(id):
    return jsonify(user_service.get_user(id))

@user_bp.route('/get', methods=['GET'])
def get_users():
    return jsonify(user_service.get_users())

@login_required
@user_bp.route('/update', methods=['PUT'])
def update_user():
    user = request.json
    result = user_service.update_user(user)
    if result == "User updated!!!":
        return jsonify(result), 200
    return jsonify(result), 404

@login_required
@user_bp.route('/delete/<int:id>', methods=['DELETE'])
def delete_user(id):
    result = user_service.delete_user(id)
    if result == "User deleted!!!":
        return jsonify(result), 200
    return jsonify(result), 404

@user_bp.route('/debug_admin')
def debug_admin():
    admin = User.query.filter_by(role=Role.ADMIN).first()
    if admin:
        return f"Admin user found: {admin.username}"
    else:
        return "No admin user found in the database"
    
@user_bp.route('/debug_admin_password')
def debug_admin_password():
    admin = User.query.filter_by(role=Role.ADMIN).first()
    if admin:
        # This is for debugging only. Never expose passwords in production!
        return f"Admin hashed password: {admin.password}"
    else:
        return "No admin user found in the database"

@user_bp.route('/view_children')
@login_required
def view_children():
    if current_user.role != Role.PARENT:
        return redirect(url_for('user.home'))
    
    children = Child.query.filter_by(parent_id=current_user.id).all()
    return render_template('UserManagement/view_children.html', children=children)

@user_bp.route('/parent_home')
@login_required
def parent_home():
    if current_user.role != Role.PARENT:
        return redirect(url_for('user.home'))
    return render_template('UserManagement/parent_home.html')


@user_bp.route('/signup')
def signup():
    return render_template('UserManagement/signup.html')

@user_bp.route('/view_learners')
@login_required
def view_learners():
    if current_user.role != Role.TEACHER:
        return redirect(url_for('user.home'))
    
    learners = Child.query.filter_by(teacher_id=current_user.id).all()
    return render_template('UserManagement/view_learners.html', learners=learners)

@user_bp.route('/home')
@login_required
def home():
    if current_user.role == Role.TEACHER:
        return redirect(url_for('user.teacher_home'))
    elif current_user.role == Role.PARENT:
        return redirect(url_for('user.parent_home'))
    elif current_user.role == Role.ADMIN:
        return redirect(url_for('user.admin_home'))
    elif current_user.role == Role.CHILD:
        return redirect(url_for('user.child_home'))
    else:
        flash("Invalid user role", "error")
        return redirect(url_for('user.login'))
    
@user_bp.route('/parent_signup_1', methods=['GET', 'POST'])
def parent_signup_1():
    if request.method == 'POST':
        kids = request.form.get('kids')
        if kids and kids.isdigit() and int(kids) > 0:
            session['kids'] = int(kids)
            return redirect(url_for('user.parent_signup_2'))
        else:
            return render_template('UserManagement/parent_signup_1.html', notification="Please enter a valid number of kids.")
    return render_template('UserManagement/parent_signup_1.html')

@user_bp.route('/parent_signup_2', methods=['GET', 'POST'])
def parent_signup_2():
    if 'kids' not in session:
        return redirect(url_for('user.parent_signup_1'), notification="Please start from the beginning.")

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = user_service.get_user_by_username(username)
        if existing_user:
            return render_template('UserManagement/parent_signup_2.html', notification="Username already exists. Please choose a different username.")

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
        return redirect(url_for('user.parent_signup_1'), notification="Please start from the beginning.")

    if request.method == 'POST':
        parent_data = session.get('parent_data', {})
        parent_data.update({
            'firstname': request.form.get('firstname'),
            'lastname': request.form.get('lastname'),
            'education_level': request.form.get('education_level'),
            'preschool_id': request.form.get('preschool_id')
        })
        session['parent_data'] = parent_data
        return redirect(url_for('user.parent_signup_4'))

    preschools = preschool_service.get_preschools()
    return render_template('UserManagement/parent_signup_3.html', preschools=preschools, EducationLevel=EducationLevel)

@user_bp.route('/parent_signup_4', methods=['GET', 'POST'])
def parent_signup_4():
    if 'parent_data' not in session or 'kids' not in session:
        return redirect(url_for('user.parent_signup_1'))

    kids = session['kids']
    parent_data = session.get('parent_data', {})
    teacher_service = TeacherService(db)
    teachers = teacher_service.get_teachers()

    if request.method == 'POST':
        try:
            # Create parent
            parent = Parent(
                firstname=parent_data.get('firstname'),
                lastname=parent_data.get('lastname'),
                username=parent_data.get('username'),
                password=generate_password_hash(parent_data.get('password')),
                email=parent_data.get('email'),
                role=Role.PARENT,
                education_level=EducationLevel(parent_data.get('education_level'))
            )
            db.session.add(parent)
            db.session.flush()

            # Track successful operations
            success_log = []
            
            for i in range(1, kids + 1):
                # Create child
                child = Child(
                    firstname=request.form[f'child_name_{i}'],
                    lastname=parent.lastname,
                    age=int(request.form[f'child_age_{i}']),
                    gender=request.form[f'child_gender_{i}'],
                    parent_id=parent.id,
                    teacher_id=int(request.form[f'child_teacher_{i}']),
                    preschool_id=parent_data.get('preschool_id'),
                    username=request.form[f'child_username_{i}'],
                    password=generate_password_hash(request.form[f'child_password_{i}']),
                    email=f"{request.form[f'child_username_{i}']}@gmail.com",
                    role=Role.CHILD,
                    race_ethnicity=request.form[f'child_race_{i}'],
                    lunch_type=LunchType(request.form[f'child_lunch_{i}']),
                    parent_education=parent.education_level
                )
                db.session.add(child)
                db.session.flush()
                success_log.append(f"Created child: {child.firstname}")

                # Get ML prediction and create learning plan
                predicted_level = predict_child_level(child.id)
                level_mapping = {0: Level.BEGINNER, 1: Level.INTERMEDIATE, 2: Level.ADVANCED}
                recommended_level = level_mapping.get(predicted_level, Level.BEGINNER)
                
                child.recommended_level = recommended_level
                
                learning_plan = LearningPlan(
                    child_id=child.id,
                    science_level=recommended_level,
                    technology_level=recommended_level,
                    engineering_level=recommended_level,
                    math_level=recommended_level,
                    story_level=recommended_level
                )
                db.session.add(learning_plan)
                db.session.flush()
                success_log.append(f"Created learning plan for: {child.firstname}")

            # Commit all changes
            db.session.commit()
            
            # Log success
            current_app.logger.info(f"Registration successful: {'; '.join(success_log)}")
            
            # Clear session and redirect
            session.clear()
            flash("Registration successful! Learning plans created for all children.", "success")
            return redirect(url_for('user.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {str(e)}")
            return render_template('UserManagement/parent_signup_4.html',
                                kids=kids,
                                teachers=teachers,
                                LunchType=LunchType,
                                error="Registration failed. Please try again.")

    return render_template('UserManagement/parent_signup_4.html',
                         kids=kids,
                         teachers=teachers,
                         LunchType=LunchType)

@user_bp.route('/teacher_signup_1', methods=['GET', 'POST'])
def teacher_signup_1():
    if request.method == 'POST':
        preschool_id = request.form['preschool_id']

        if preschool_id:
            session['preschool_id'] = preschool_id
            return redirect(url_for('user.teacher_signup_2'))
        else:
            return render_template('UserManagement/teacher_signup_1.html', preschools=preschools,
                                   notification="Please select a preschool.")

    preschools = PreschoolService.get_preschools()
    return render_template('UserManagement/teacher_signup_1.html', preschools=preschools)


@user_bp.route('/teacher_signup_2', methods=['GET', 'POST'])
def teacher_signup_2():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        session['teacher_data'] = {
            'username': username,
            'email': email,
            'password': password
        }

        return redirect(url_for('user.teacher_signup_3'))
    return render_template('UserManagement/teacher_signup_2.html')


@user_bp.route('/teacher_signup_3', methods=['GET', 'POST'])
def teacher_signup_3():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']

        teacher_data = session.get('teacher_data', {})
        preschool_id = session.get('preschool_id')

        # Create the teacher
        teacher = Teacher(
            username=teacher_data['username'],
            password=generate_password_hash(teacher_data['password']),
            email=teacher_data['email'],
            role=Role.TEACHER,
            firstname=firstname,
            lastname=lastname,
            preschool_id=preschool_id
        )
        db.session.add(teacher)
        db.session.commit()

        session.pop('teacher_data', None)
        session.pop('preschool_id', None)

        flash("Teacher signup successful!", "success")
        return redirect(url_for('user.login'))
    return render_template('UserManagement/teacher_signup_3.html')               

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = None
        for UserModel in [User, Parent, Teacher, Child]:
            user = UserModel.query.filter_by(username=username).first()
            if user:
                break

        if user and check_password_hash(user.password, password):
            login_user(user)
            #flash(f"Welcome, {user.username}!", 'success')
            
            if isinstance(user, User) and user.role == Role.ADMIN:
                return redirect(url_for('user.admin_home'))
            elif isinstance(user, Child):
                return redirect(url_for('user.child_home'))
            elif isinstance(user, Parent):
                return redirect(url_for('user.parent_home'))
            elif isinstance(user, Teacher):
                return redirect(url_for('user.teacher_home'))
        else:
            return render_template('UserManagement/login.html', notification="Invalid username or password")

    return render_template('UserManagement/login.html')

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('user.login'))

@user_bp.route('/child_home')
@login_required
def child_home():
    return render_template('UserManagement/child_home.html')

@user_bp.route('/teacher_home')
@login_required
def teacher_home():
    return render_template('UserManagement/teacher_home.html')

@user_bp.route('/admin_home')
@login_required
def admin_home():
    return render_template('UserManagement/admin_home.html')