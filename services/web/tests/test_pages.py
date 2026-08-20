"""Do pages render, and only for the right role?

The failure this guards against is specific to the split: a template traverses
something the api does not send, Jinja renders it as empty rather than raising,
and the page looks fine while being wrong. So these assert on content, not just
on status codes.
"""
import pytest
from conftest import login

# path, roles allowed
MATRIX = [
    ('/users/parent_home', {'parent'}),
    ('/users/teacher_home', {'teacher'}),
    ('/users/admin_home', {'admin'}),
    ('/users/child_home', {'child'}),
    ('/users/view_children', {'parent'}),
    ('/users/view_learners', {'teacher'}),
    ('/activities', {'child'}),
    ('/stories', {'child'}),
    ('/learning-content', {'child'}),
    ('/parent/progress', {'parent'}),
    ('/parent/results', {'parent'}),
    ('/teacher/progress', {'teacher'}),
    ('/teacher/results', {'teacher'}),
    ('/learning_plans/manage', {'teacher'}),
    ('/feedbacks/feedback', {'parent', 'teacher'}),
    ('/feedbacks/feedback/view', {'parent', 'teacher'}),
    ('/feedbacks/feedback/past', {'parent', 'teacher'}),
    ('/admin/home', {'admin'}),
    ('/admin/modify_content', {'admin'}),
    ('/admin/view_user_data', {'admin'}),
    ('/admin/add_activity', {'admin'}),
    ('/admin/add_story', {'admin'}),
    ('/preschools/admin/preschools', {'admin'}),
]

ROLES = ['parent', 'teacher', 'child', 'admin']


@pytest.mark.parametrize('path,allowed', MATRIX)
@pytest.mark.parametrize('role', ROLES)
def test_role_access(client, role, path, allowed):
    login(client, role)
    response = client.get(path)
    if role in allowed:
        assert response.status_code == 200, f"{role} should see {path}"
    else:
        # Guards redirect rather than 403 so a person gets a page, not a wall.
        assert response.status_code == 302, f"{role} should not see {path}"


@pytest.mark.parametrize('path', [p for p, _ in MATRIX])
def test_every_page_requires_a_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert '/users/login' in response.headers['Location']


# --------------------------------------------------- content, not just 200s

def test_public_pages_render_anonymously(client):
    for path in ('/', '/users/login', '/users/signup', '/healthz'):
        assert client.get(path).status_code == 200, path


def test_child_sees_activity_titles(client):
    login(client, 'child')
    body = client.get('/activities').get_data(as_text=True)
    assert 'Counting to Ten' in body


def test_child_sees_story_titles(client):
    login(client, 'child')
    body = client.get('/stories').get_data(as_text=True)
    assert 'Ben the Bear' in body


def test_parent_progress_names_the_child(client):
    login(client, 'parent')
    body = client.get('/parent/progress').get_data(as_text=True)
    assert 'Ari' in body
    assert 'Counting to Ten' in body


def test_results_render_a_date_not_a_raw_timestamp(client):
    """The |datetime filter exists because a JSON string has no .strftime, and
    Jinja renders the failed attribute as empty rather than raising."""
    login(client, 'parent')
    body = client.get('/parent/results').get_data(as_text=True)
    assert '2026-08-17' in body
    assert '2026-08-17T12:10:28+00:00' not in body


def test_feedback_inbox_shows_the_sender(client):
    login(client, 'parent')
    body = client.get('/feedbacks/feedback/view').get_data(as_text=True)
    assert 'Tina' in body
    assert 'Great week' in body


def test_admin_content_table_lists_both_kinds(client):
    login(client, 'admin')
    body = client.get('/admin/modify_content').get_data(as_text=True)
    assert 'Counting to Ten' in body
    assert 'Ben the Bear' in body


def test_content_images_point_at_the_api(client):
    """Uploads live beside the api, not in web's static folder. Pointing an
    <img> at /static would 404 for anything uploaded after the split."""
    login(client, 'child')
    body = client.get('/activities').get_data(as_text=True)
    assert '/api/media/Basic_counting.jpeg' in body
    assert 'static/images/Basic_counting.jpeg' not in body


# --------------------------------------------------------------- sessions

def test_login_rejects_a_bad_password(client):
    response = client.post('/users/login',
                           data={'username': 'parent', 'password': 'wrong'})
    assert response.status_code == 401
    assert 'Invalid username or password' in response.get_data(as_text=True)


def test_logout_clears_the_token(client):
    login(client, 'parent')
    client.get('/users/logout')
    with client.session_transaction() as session:
        assert 'api_token' not in session
    assert client.get('/users/parent_home').status_code == 302


def test_the_token_is_stored_on_login(client):
    login(client, 'parent')
    with client.session_transaction() as session:
        assert session['api_token'] == 'tok-3'
