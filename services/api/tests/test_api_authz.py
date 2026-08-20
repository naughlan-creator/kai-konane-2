"""Who may touch what.

The rest of the suite runs as an administrator, which is allowed everywhere --
so these tests are the only ones that would catch a missing check. Each one
describes an attack that worked before app/api/authz.py existed.
"""
import pytest
from app.api.auth_seam import issue_token
from app.models import User
from conftest import flask_app


def token_for(username):
    with flask_app.app_context():
        return issue_token(User.query.filter_by(username=username).first())


@pytest.fixture(scope="module")
def parent_token(app):
    return token_for("parent")


@pytest.fixture(scope="module")
def teacher_token(app):
    return token_for("teacher")


@pytest.fixture(scope="module")
def child_token(app):
    return token_for("child")


@pytest.fixture(scope="module")
def outsider_token(app, ids):
    return token_for("outsider")


def as_(client, token):
    client.token = token
    return client


# ------------------------------------------------- privilege escalation

def test_a_parent_cannot_change_another_account(client, parent_token, ids):
    """The hole this module was written for: a parent token could PATCH the
    administrator's password and then sign in as them."""
    response = as_(client, parent_token).patch('/api/users/1',
                                               json={'password': 'pwned'})
    assert response.status_code == 403


def test_a_parent_cannot_delete_a_user(client, parent_token, ids):
    assert as_(client, parent_token).delete(
        f"/api/users/{ids['teacher']}").status_code == 403


def test_a_parent_cannot_list_every_user(client, parent_token):
    assert as_(client, parent_token).get('/api/users').status_code == 403


def test_a_user_may_edit_themselves(client, parent_token, ids):
    response = as_(client, parent_token).patch(
        f"/api/users/{ids['parent']}", json={'email': 'pania@x.local'})
    assert response.status_code == 200


# --------------------------------------------------- reading other families

def test_a_parent_cannot_read_another_familys_child(client, parent_token, ids):
    assert as_(client, parent_token).get(
        f"/api/children/{ids['outsider_child']}").status_code == 403


def test_a_parent_cannot_list_another_parents_children(client, parent_token, ids):
    assert as_(client, parent_token).get(
        f"/api/children?parent_id={ids['outsider']}").status_code == 403


def test_a_parent_cannot_read_another_childs_progress(client, parent_token, ids):
    for path in ('progress', 'results', 'stem-levels'):
        response = as_(client, parent_token).get(
            f"/api/children/{ids['outsider_child']}/{path}")
        assert response.status_code == 403, path


def test_a_parent_cannot_read_another_childs_plan(client, parent_token, ids):
    assert as_(client, parent_token).get(
        f"/api/learning-plans/child/{ids['outsider_child']}").status_code == 403


def test_a_teacher_cannot_read_another_teachers_roster(client, teacher_token, ids):
    assert as_(client, teacher_token).get(
        f"/api/teachers/{ids['other_teacher']}/students").status_code == 403


def test_a_teacher_cannot_read_another_teachers_progress(client, teacher_token, ids):
    assert as_(client, teacher_token).get(
        f"/api/progress?teacher_id={ids['other_teacher']}").status_code == 403


def test_a_child_cannot_read_another_child(client, child_token, ids):
    assert as_(client, child_token).get(
        f"/api/children/{ids['child2']}").status_code == 403


def test_a_child_may_read_themselves(client, child_token, ids):
    assert as_(client, child_token).get(
        f"/api/children/{ids['child']}").status_code == 200


# ------------------------------------------------------- content authoring

@pytest.mark.parametrize('method,path,body', [
    ('post', '/api/activities', {'title': 'x'}),
    ('patch', '/api/activities/1', {'title': 'x'}),
    ('delete', '/api/activities/1', None),
    ('post', '/api/stories', {'title': 'x'}),
    ('patch', '/api/stories/1', {'title': 'x'}),
    ('delete', '/api/stories/1', None),
    ('post', '/api/preschools', {'name': 'x'}),
    ('patch', '/api/preschools/1', {'name': 'x'}),
    ('delete', '/api/preschools/1', None),
])
def test_authoring_is_admin_only(client, parent_token, method, path, body):
    """A signed-in parent is not an author. Before this, any token could
    rewrite the whole content library."""
    call = getattr(as_(client, parent_token), method)
    response = call(path, json=body) if body is not None else call(path)
    assert response.status_code == 403


# --------------------------------------------------------------- feedback

def test_you_cannot_send_as_someone_else(client, parent_token, ids):
    """Otherwise any token could forge a message from a head teacher."""
    response = as_(client, parent_token).post('/api/feedback', json={
        'sender_id': ids['teacher'], 'recipient_id': ids['outsider'],
        'subject': 'Forged', 'content': 'Not from me',
    })
    assert response.status_code == 403


def test_you_cannot_read_someone_elses_inbox(client, parent_token, ids):
    assert as_(client, parent_token).get(
        f"/api/feedback?recipient_id={ids['teacher']}").status_code == 403
    assert as_(client, parent_token).get(
        f"/api/feedback?participant_id={ids['teacher']}").status_code == 403


def test_you_may_read_your_own_inbox(client, parent_token, ids):
    assert as_(client, parent_token).get(
        f"/api/feedback?recipient_id={ids['parent']}").status_code == 200


# ------------------------------------------------ the checks are not blanket

def test_a_parent_still_reaches_their_own_family(client, parent_token, ids):
    """Deny-by-default must not deny the legitimate case -- the failure mode of
    a security patch is locking out the people it was meant to protect."""
    for path in (
        f"/api/children?parent_id={ids['parent']}",
        f"/api/children/{ids['child']}",
        f"/api/children/{ids['child']}/progress",
        f"/api/children/{ids['child']}/results",
        f"/api/children/{ids['child']}/stem-levels",
        f"/api/learning-plans/child/{ids['child']}",
        f"/api/parents/{ids['parent']}/children",
    ):
        assert as_(client, parent_token).get(path).status_code == 200, path


def test_a_teacher_still_reaches_their_own_class(client, teacher_token, ids):
    for path in (
        f"/api/children?teacher_id={ids['teacher']}",
        f"/api/teachers/{ids['teacher']}/students",
        f"/api/progress?teacher_id={ids['teacher']}",
        f"/api/results?teacher_id={ids['teacher']}",
        f"/api/children/{ids['child']}/stem-levels",
    ):
        assert as_(client, teacher_token).get(path).status_code == 200, path


def test_a_correspondent_may_read_the_other_partys_name(client, parent_token, ids):
    """The feedback picker shows the teacher's name, so a parent must be able to
    read that one account -- but only because they share a learner."""
    assert as_(client, parent_token).get(
        f"/api/users/{ids['teacher']}").status_code == 200
    assert as_(client, parent_token).get(
        f"/api/users/{ids['other_teacher']}").status_code == 403
