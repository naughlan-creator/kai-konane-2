"""Profile edits, and the ways they are allowed to fail.

The happy paths were covered indirectly; the failure paths were not covered at
all, which left ParentService at 27%. Every test here goes through an endpoint
rather than calling a service directly -- a failure mode only matters if a
client can reach it.
"""
from conftest import flask_app

from app.models import Child, Parent


# ------------------------------------------------------------- parents

def test_updating_a_parent_moves_their_children_too(client, ids):
    """Child.parent_education is a snapshot the level model reads. If it does
    not move with the parent, predictions drift from reality silently."""
    response = client.patch(f"/api/parents/{ids['parent']}", json={
        'firstname': 'Pania', 'lastname': 'Rewi',
        'education_level': 'MASTERS_DEGREE',
    })
    assert response.status_code == 200
    assert response.get_json()['parent']['education_level']['name'] == 'MASTERS_DEGREE'

    with flask_app.app_context():
        parent = Parent.query.filter_by(username='parent').first()
        assert parent.children
        for child in parent.children:
            assert child.parent_education.name == 'MASTERS_DEGREE'


def test_a_bad_education_level_is_rejected(client, ids):
    response = client.patch(f"/api/parents/{ids['parent']}",
                            json={'firstname': 'P', 'lastname': 'R',
                                  'education_level': 'DOCTOR_OF_VIBES'})
    assert response.status_code == 400


def test_omitting_the_education_level_keeps_the_current_one(client, ids):
    """coerce() falls back to the existing value, so a form that does not
    include the field must not blank it."""
    before = client.get(f"/api/users/{ids['parent']}").get_json()['user']
    response = client.patch(f"/api/parents/{ids['parent']}",
                            json={'firstname': 'Pania', 'lastname': 'Rewi'})
    assert response.status_code == 200
    assert (response.get_json()['parent']['education_level']['name']
            == before['education_level']['name'])


def test_updating_a_parent_that_does_not_exist(client):
    assert client.patch('/api/parents/999999',
                        json={'firstname': 'X', 'lastname': 'Y',
                              'education_level': 'HIGH_SCHOOL'}).status_code == 404


# -------------------------------------------------------------- children

def test_updating_a_child(client, ids):
    response = client.patch(f"/api/children/{ids['child']}", json={
        'firstname': 'Ari', 'lastname': 'Rewi', 'age': 6,
        'gender': 'Female', 'race_ethnicity': 'group B',
        'lunch_type': 'FREE_REDUCED',
    })
    assert response.status_code == 200
    child = response.get_json()['child']
    assert child['age'] == 6
    assert child['lunch_type']['name'] == 'FREE_REDUCED'


def test_a_non_numeric_age_is_rejected(client, ids):
    response = client.patch(f"/api/children/{ids['child']}", json={
        'firstname': 'Ari', 'lastname': 'Rewi', 'age': 'five',
        'gender': 'Female', 'race_ethnicity': None, 'lunch_type': 'STANDARD',
    })
    assert response.status_code == 400

    with flask_app.app_context():
        # The rejected write must not have partially applied.
        assert Child.query.filter_by(username='child').first().age != 'five'


def test_a_bad_lunch_type_is_rejected(client, ids):
    response = client.patch(f"/api/children/{ids['child']}", json={
        'firstname': 'Ari', 'lastname': 'Rewi', 'age': 5,
        'gender': 'Female', 'race_ethnicity': None, 'lunch_type': 'BANQUET',
    })
    assert response.status_code == 400


def test_updating_a_child_that_does_not_exist(client):
    assert client.patch('/api/children/999999',
                        json={'firstname': 'X', 'age': 5}).status_code == 404


# --------------------------------------------------------------- teachers

def test_updating_a_teacher(client, ids):
    response = client.patch(f"/api/teachers/{ids['teacher']}",
                            json={'firstname': 'Tina', 'lastname': 'Kahu'})
    assert response.status_code == 200
    assert response.get_json()['teacher']['firstname'] == 'Tina'


def test_updating_a_teacher_that_does_not_exist(client):
    assert client.patch('/api/teachers/999999',
                        json={'firstname': 'X', 'lastname': 'Y'}).status_code == 404


# ------------------------------------------------------------ accounts

def test_a_taken_username_is_a_conflict(client, ids):
    """409, not 500. The database would raise IntegrityError; the service
    checks first so the caller gets a message it can show a person."""
    response = client.patch(f"/api/users/{ids['parent']}",
                            json={'username': 'teacher'})
    assert response.status_code == 409
    assert 'username' in response.get_json()['error'].lower()


def test_a_taken_email_is_a_conflict(client, ids):
    response = client.patch(f"/api/users/{ids['parent']}",
                            json={'email': 'teacher@kaikonane.local'})
    assert response.status_code == 409
    assert 'email' in response.get_json()['error'].lower()


def test_keeping_your_own_username_is_not_a_conflict(client, ids):
    """The uniqueness check must exclude the row being edited, or saving a form
    without changing the username fails against itself."""
    current = client.get(f"/api/users/{ids['parent']}").get_json()['user']
    response = client.patch(f"/api/users/{ids['parent']}",
                            json={'username': current['username'],
                                  'email': current['email']})
    assert response.status_code == 200


def test_updating_a_user_that_does_not_exist(client):
    assert client.patch('/api/users/999999',
                        json={'username': 'ghost'}).status_code == 404


def test_changing_a_password_lets_the_new_one_log_in(client, anon_client, ids):
    client.patch(f"/api/users/{ids['child2']}", json={'password': 'newpassword'})
    ok = anon_client.post('/api/auth/login',
                          json={'username': 'child2', 'password': 'newpassword'})
    assert ok.status_code == 200
    old = anon_client.post('/api/auth/login',
                           json={'username': 'child2', 'password': 'pw'})
    assert old.status_code == 401
