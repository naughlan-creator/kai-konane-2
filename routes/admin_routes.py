from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from config import db
from models.learning_content import LCTYPE
from models.user import Role, User
from routes.auth import admin_required
from services.activity_service import ActivityService
from services.errors import ServiceError
from services.media import library_images
from services.story_service import StoryService

admin_bp = Blueprint('admin', __name__)

activity_service = ActivityService()
story_service = StoryService()

# Generous caps -- the forms are dynamic, so these only bound the parse loop.
MAX_QUESTIONS = 100
MAX_ANSWERS = 10
MAX_PAGES = 100


def _collect_questions(form):
    """Read the repeated question_N / answer_N_M fields out of a form.

    The N and M are contiguous from 1 because the editor renumbers every row
    after any add, remove or reorder.
    """
    questions_data = []
    for i in range(1, MAX_QUESTIONS + 1):
        question_key = f'question_{i}'
        if question_key not in form:
            break

        # A radio group posts the index of the chosen answer for this question.
        correct_index = form.get(f'correct_{i}')

        answers = []
        for j in range(1, MAX_ANSWERS + 1):
            answer_key = f'answer_{i}_{j}'
            if answer_key not in form:
                break
            answers.append({
                'id': form.get(f'answer_id_{i}_{j}') or None,
                'content': form[answer_key],
                # Accept the older per-answer checkbox too, so an existing
                # bookmarked form still submits something meaningful.
                'is_correct': correct_index == str(j) or f'correct_{i}_{j}' in form,
            })

        questions_data.append({
            # Without the id the update path cannot tell an edited question from
            # a new one, and every save duplicates the whole question set.
            'id': form.get(f'question_id_{i}') or None,
            'content': form[question_key],
            'answers': answers,
        })
    return questions_data


def _collect_pages(form, files):
    pages = []
    for i in range(1, MAX_PAGES + 1):
        page_content_key = f'page_content_{i}'
        if page_content_key not in form:
            break
        pages.append({
            'id': form.get(f'page_id_{i}') or None,
            'line_of_page': form[page_content_key],
            'image': files.get(f'page_image_{i}'),
            'existing_image': form.get(f'page_existing_{i}') or None,
        })
    return pages


@admin_bp.route('/admin/home')
@admin_required
def admin_home():
    return render_template('UserManagement/admin_home.html')


@admin_bp.route('/admin/view_content')
@admin_required
def view_content():
    learning_content = []

    for activity in activity_service.get_activities():
        learning_content.append({
            'name': activity.title,
            'content_type': LCTYPE.ACTIVITY.value,
            'stem_code': activity.stem_code.value if activity.stem_code else '',
        })

    for story in story_service.get_stories():
        learning_content.append({
            'name': story.title,
            'content_type': LCTYPE.STORY.value,
            'stem_code': '',  # Stories don't have STEM codes
        })

    return render_template('ContentManagement/view_learning_content.html',
                           learning_content=learning_content)


@admin_bp.route('/admin/add_content')
@admin_required
def add_content():
    return render_template('ContentManagement/add_content.html')


@admin_bp.route('/admin/add_activity', methods=['GET', 'POST'])
@admin_required
def add_activity():
    if request.method == 'POST':
        try:
            activity = activity_service.add_activity(
                title=request.form.get('activity_title'),
                stem_code=request.form.get('stem_code'),
                level=request.form.get('level'),
                cover_image=request.files.get('cover_image'),
                questions_data=_collect_questions(request.form),
                description=request.form.get('description'),
                existing_cover=request.form.get('existing_cover'),
            )
        except ServiceError as e:
            # Redisplay rather than discarding what the author typed.
            flash(str(e), 'error')
            return render_template('ContentManagement/activity_form.html',
                                   images=library_images())

        flash('Added ' + activity.title, 'success')
        return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/activity_form.html', images=library_images())


@admin_bp.route('/admin/add_story', methods=['GET', 'POST'])
@admin_required
def add_story():
    if request.method == 'POST':
        try:
            story = story_service.add_story(
                title=request.form.get('story_title'),
                level=request.form.get('level'),
                cover_image=request.files.get('cover_image'),
                pages=_collect_pages(request.form, request.files),
                description=request.form.get('description'),
                existing_cover=request.form.get('existing_cover'),
            )
        except ServiceError as e:
            flash(str(e), 'error')
            return render_template('ContentManagement/story_form.html',
                                   images=library_images())

        flash('Added ' + story.title, 'success')
        return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/story_form.html', images=library_images())


@admin_bp.route('/admin/modify_content')
@admin_required
def modify_content():
    learning_content = []

    for activity in activity_service.get_activities():
        learning_content.append({
            'id': activity.id,
            'name': activity.title,
            'content_type': LCTYPE.ACTIVITY.value,
            'stem_code': activity.stem_code.value if activity.stem_code else '',
            'update_url': url_for('admin.update_activity', activity_id=activity.id),
            'delete_url': url_for('admin.delete_activity', activity_id=activity.id)
        })

    for story in story_service.get_stories():
        learning_content.append({
            'id': story.id,
            'name': story.title,
            'content_type': LCTYPE.STORY.value,
            'stem_code': '',  # Stories don't have STEM codes
            'update_url': url_for('admin.update_story', story_id=story.id),
            'delete_url': url_for('admin.delete_story', story_id=story.id)
        })

    return render_template('ContentManagement/modify_content.html',
                           learning_content=learning_content)


@admin_bp.route('/admin/update_activity/<int:activity_id>', methods=['GET', 'POST'])
@admin_required
def update_activity(activity_id):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        flash('Activity not found.', 'error')
        # 'admin.view_activities' does not exist; this used to raise a BuildError.
        return redirect(url_for('admin.modify_content'))

    if request.method == 'POST':
        try:
            activity_service.update_activity(
                activity_id,
                title=request.form.get('activity_title'),
                stem_code=request.form.get('stem_code'),
                level=request.form.get('level'),
                cover_image=request.files.get('cover_image'),
                questions_data=_collect_questions(request.form),
                description=request.form.get('description'),
                existing_cover=request.form.get('existing_cover'),
            )
        except ServiceError as e:
            flash(str(e), 'error')
        else:
            flash('Activity updated', 'success')
            return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/activity_form.html',
                           activity=activity, images=library_images())


@admin_bp.route('/admin/update_story/<int:story_id>', methods=['GET', 'POST'])
@admin_required
def update_story(story_id):
    story = story_service.get_story(story_id)
    if not story:
        flash('Story not found.', 'error')
        return redirect(url_for('admin.modify_content'))

    if request.method == 'POST':
        try:
            story_service.update_story(
                story_id,
                title=request.form.get('story_title'),
                level=request.form.get('level'),
                cover_image=request.files.get('cover_image'),
                pages=_collect_pages(request.form, request.files),
                description=request.form.get('description'),
                existing_cover=request.form.get('existing_cover'),
            )
        except ServiceError as e:
            flash(str(e), 'error')
        else:
            flash('Story updated', 'success')
            return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/story_form.html',
                           story=story, images=library_images())


@admin_bp.route('/admin/delete_activity/<int:activity_id>', methods=['GET', 'POST'])
@admin_required
def delete_activity(activity_id):
    try:
        activity = activity_service.delete_activity(activity_id)
    except ServiceError as e:
        flash(str(e), 'error')
    else:
        flash('Deleted ' + activity.title, 'success')
    return redirect(url_for('admin.modify_content'))


@admin_bp.route('/admin/delete_story/<int:story_id>', methods=['GET', 'POST'])
@admin_required
def delete_story(story_id):
    try:
        story = story_service.delete_story(story_id)
    except ServiceError as e:
        flash(str(e), 'error')
    else:
        flash('Deleted ' + story.title, 'success')
    return redirect(url_for('admin.modify_content'))


@admin_bp.route('/admin/view_user_data')
@admin_required
def view_user_data():
    users = User.query.order_by(User.id).all()
    return render_template('UserManagement/view_user_data.html', users=users)


@admin_bp.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()

        clash = User.query.filter(User.id != user.id,
                                  (User.username == username) | (User.email == email)).first()
        if clash:
            flash('That username or email is already in use', 'error')
            return render_template('UserManagement/edit_user.html', user=user, roles=Role)

        role = Role.coerce(request.form.get('role'))
        if role is None:
            flash('Please choose a valid role', 'error')
            return render_template('UserManagement/edit_user.html', user=user, roles=Role)

        user.username = username
        user.email = email
        user.role = role

        if request.form.get('password'):
            user.set_password(request.form['password'])

        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin.view_user_data'))

    return render_template('UserManagement/edit_user.html', user=user, roles=Role)


@admin_bp.route('/admin/delete_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == Role.ADMIN:
        flash('Cannot delete admin users', 'error')
        return redirect(url_for('admin.view_user_data'))
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin.view_user_data'))

    if user.type == 'parent' and user.children:
        flash("Deleting this parent also removes their learners. "
              "Remove the learners first if you want to keep them.", 'error')
        return redirect(url_for('admin.view_user_data'))

    # Dependent rows cascade from the model definitions now, so there is no
    # table-by-table cleanup to get wrong here.
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.view_user_data'))
