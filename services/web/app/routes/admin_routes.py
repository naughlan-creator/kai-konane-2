"""Content authoring and user administration.

Images are the only thing here that is not JSON. An upload goes to the api's
`POST /media` first, which returns a filename; that name is then sent with the
content itself. So a picture crosses the boundary once, as bytes, and every
later reference to it is a short string.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import api_client
from app.routes.auth import admin_required

admin_bp = Blueprint('admin', __name__)

# Generous caps -- the forms are dynamic, so these only bound the parse loop.
MAX_QUESTIONS = 100
MAX_ANSWERS = 10
MAX_PAGES = 100

ACTIVITY = 'Activity'
STORY = 'Story'


def _library_images():
    try:
        return api_client.get('media')['images']
    except api_client.ApiError:
        return []


def _upload(storage, fallback=None):
    """Send one image to the api and return its filename.

    Falls back to the name the form already carried, which is what stops an
    edit that does not touch the picture from wiping it.
    """
    if storage is None or not getattr(storage, 'filename', ''):
        return fallback
    try:
        return api_client.post_file('media', 'image', storage)['filename']
    except api_client.ApiError:
        # An unusable upload must not discard everything else the author typed.
        return fallback


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
            'image_filename': _upload(files.get(f'page_image_{i}'),
                                      form.get(f'page_existing_{i}') or None),
        })
    return pages


def _content_rows(with_urls=False):
    """Activities and stories in one list, as the two content tables want them."""
    rows = []
    for activity in api_client.get('activities')['activities']:
        row = {
            'id': activity['id'],
            'name': activity['title'],
            'content_type': ACTIVITY,
            'stem_code': (activity.get('stem_code') or {}).get('value', ''),
        }
        if with_urls:
            row['update_url'] = url_for('admin.update_activity',
                                        activity_id=activity['id'])
            row['delete_url'] = url_for('admin.delete_activity',
                                        activity_id=activity['id'])
        rows.append(row)

    for story in api_client.get('stories')['stories']:
        row = {
            'id': story['id'],
            'name': story['title'],
            'content_type': STORY,
            'stem_code': '',  # Stories don't have STEM codes
        }
        if with_urls:
            row['update_url'] = url_for('admin.update_story', story_id=story['id'])
            row['delete_url'] = url_for('admin.delete_story', story_id=story['id'])
        rows.append(row)

    return rows


@admin_bp.route('/admin/home')
@admin_required
def admin_home():
    return render_template('UserManagement/admin_home.html')


@admin_bp.route('/admin/view_content')
@admin_required
def view_content():
    return render_template('ContentManagement/view_learning_content.html',
                           learning_content=_content_rows())


@admin_bp.route('/admin/add_content')
@admin_required
def add_content():
    return render_template('ContentManagement/add_content.html')


@admin_bp.route('/admin/modify_content')
@admin_required
def modify_content():
    return render_template('ContentManagement/modify_content.html',
                           learning_content=_content_rows(with_urls=True))


@admin_bp.route('/admin/add_activity', methods=['GET', 'POST'])
@admin_required
def add_activity():
    if request.method == 'POST':
        try:
            created = api_client.post('activities', json={
                'title': request.form.get('activity_title'),
                'stem_code': request.form.get('stem_code'),
                'level': request.form.get('level'),
                'description': request.form.get('description'),
                'cover_image': _upload(request.files.get('cover_image'),
                                       request.form.get('existing_cover')),
                'questions': _collect_questions(request.form),
            })
        except api_client.ApiError as e:
            # Redisplay rather than discarding what the author typed.
            flash(e.message, 'error')
            return render_template('ContentManagement/activity_form.html',
                                   images=_library_images())

        flash('Added ' + created['activity']['title'], 'success')
        return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/activity_form.html',
                           images=_library_images())


@admin_bp.route('/admin/update_activity/<int:activity_id>',
                methods=['GET', 'POST'])
@admin_required
def update_activity(activity_id):
    try:
        activity = api_client.get(f'activities/{activity_id}')['activity']
    except api_client.ApiNotFound:
        flash('Activity not found.', 'error')
        # 'admin.view_activities' does not exist; this used to raise a BuildError.
        return redirect(url_for('admin.modify_content'))

    if request.method == 'POST':
        try:
            api_client.patch(f'activities/{activity_id}', json={
                'title': request.form.get('activity_title'),
                'stem_code': request.form.get('stem_code'),
                'level': request.form.get('level'),
                'description': request.form.get('description'),
                'cover_image': _upload(request.files.get('cover_image'),
                                       request.form.get('existing_cover')),
                'questions': _collect_questions(request.form),
            })
        except api_client.ApiError as e:
            flash(e.message, 'error')
        else:
            flash('Activity updated', 'success')
            return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/activity_form.html',
                           activity=activity, images=_library_images())


@admin_bp.route('/admin/add_story', methods=['GET', 'POST'])
@admin_required
def add_story():
    if request.method == 'POST':
        try:
            created = api_client.post('stories', json={
                'title': request.form.get('story_title'),
                'level': request.form.get('level'),
                'description': request.form.get('description'),
                'cover_image': _upload(request.files.get('cover_image'),
                                       request.form.get('existing_cover')),
                'pages': _collect_pages(request.form, request.files),
            })
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('ContentManagement/story_form.html',
                                   images=_library_images())

        flash('Added ' + created['story']['title'], 'success')
        return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/story_form.html',
                           images=_library_images())


@admin_bp.route('/admin/update_story/<int:story_id>', methods=['GET', 'POST'])
@admin_required
def update_story(story_id):
    try:
        story = api_client.get(f'stories/{story_id}')['story']
    except api_client.ApiNotFound:
        flash('Story not found.', 'error')
        return redirect(url_for('admin.modify_content'))

    if request.method == 'POST':
        try:
            api_client.patch(f'stories/{story_id}', json={
                'title': request.form.get('story_title'),
                'level': request.form.get('level'),
                'description': request.form.get('description'),
                'cover_image': _upload(request.files.get('cover_image'),
                                       request.form.get('existing_cover')),
                'pages': _collect_pages(request.form, request.files),
            })
        except api_client.ApiError as e:
            flash(e.message, 'error')
        else:
            flash('Story updated', 'success')
            return redirect(url_for('admin.modify_content'))

    return render_template('ContentManagement/story_form.html',
                           story=story, images=_library_images())


@admin_bp.route('/admin/delete_activity/<int:activity_id>',
                methods=['GET', 'POST'])
@admin_required
def delete_activity(activity_id):
    try:
        deleted = api_client.delete(f'activities/{activity_id}')
    except api_client.ApiError as e:
        flash(e.message, 'error')
    else:
        flash('Deleted ' + deleted['deleted']['title'], 'success')
    return redirect(url_for('admin.modify_content'))


@admin_bp.route('/admin/delete_story/<int:story_id>', methods=['GET', 'POST'])
@admin_required
def delete_story(story_id):
    try:
        deleted = api_client.delete(f'stories/{story_id}')
    except api_client.ApiError as e:
        flash(e.message, 'error')
    else:
        flash('Deleted ' + deleted['deleted']['title'], 'success')
    return redirect(url_for('admin.modify_content'))


@admin_bp.route('/admin/view_user_data')
@admin_required
def view_user_data():
    users = api_client.get('users')['users']
    return render_template('UserManagement/view_user_data.html', users=users)


@admin_bp.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    try:
        user = api_client.get(f'users/{user_id}')['user']
    except api_client.ApiNotFound:
        flash('User not found', 'error')
        return redirect(url_for('admin.view_user_data'))

    roles = api_client.get('enums')['Role']

    if request.method == 'POST':
        try:
            # The api raises Conflict on a taken username or email, which is
            # the uniqueness check this route used to run by hand.
            api_client.patch(f'users/{user_id}', json={
                'username': (request.form.get('username') or '').strip(),
                'email': (request.form.get('email') or '').strip(),
                'password': request.form.get('password') or None,
            })
        except api_client.ApiConflict:
            flash('That username or email is already in use', 'error')
            return render_template('UserManagement/edit_user.html',
                                   user=user, roles=roles)
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('UserManagement/edit_user.html',
                                   user=user, roles=roles)

        flash('User updated successfully', 'success')
        return redirect(url_for('admin.view_user_data'))

    return render_template('UserManagement/edit_user.html',
                           user=user, roles=roles)


@admin_bp.route('/admin/delete_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin.view_user_data'))

    try:
        user = api_client.get(f'users/{user_id}')['user']
    except api_client.ApiNotFound:
        flash('User not found', 'error')
        return redirect(url_for('admin.view_user_data'))

    if (user.get('role') or {}).get('name') == 'ADMIN':
        flash('Cannot delete admin users', 'error')
        return redirect(url_for('admin.view_user_data'))

    if user.get('type') == 'parent' and user.get('children'):
        flash("Deleting this parent also removes their learners. "
              "Remove the learners first if you want to keep them.", 'error')
        return redirect(url_for('admin.view_user_data'))

    try:
        api_client.delete(f'users/{user_id}')
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('admin.view_user_data'))

    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.view_user_data'))
