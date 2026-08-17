"""Auth, users, preschools, plans, progress and feedback over JSON.

Paired with test_api_content.py, these two files cover the whole contract in
docs/architecture.md. Assertions are on shape and invariants rather than
absolute counts -- the seeded database is shared and mutable.
"""
from conftest import flask_app

# ------------------------------------------------------------------- auth

def test_login_returns_the_user_without_a_password(client):
    response = client.post('/api/auth/login',
                           json={'username': 'parent', 'password': 'pw'})
    assert response.status_code == 200
    user = response.get_json()['user']
    assert user['username'] == 'parent'
    assert user['role'] == {'name': 'PARENT', 'value': 'PARENT'}
    # The hash must never cross the wire, under any key.
    assert 'password' not in user
    assert not any('password' in key for key in user)


def test_login_embeds_children_for_a_parent(client):
    """web's user_loader needs these in one call, not one per reference."""
    user = client.post('/api/auth/login',
                       json={'username': 'parent', 'password': 'pw'}
                       ).get_json()['user']
    assert len(user['children']) == 2
    assert {c['username'] for c in user['children']} == {'child', 'child2'}


def test_login_embeds_students_for_a_teacher(client):
    user = client.post('/api/auth/login',
                       json={'username': 'teacher', 'password': 'pw'}
                       ).get_json()['user']
    assert len(user['students']) >= 2


def test_bad_password_is_401_and_vague(client):
    response = client.post('/api/auth/login',
                           json={'username': 'parent', 'password': 'wrong'})
    assert response.status_code == 401
    # Must not reveal whether the username exists.
    assert response.get_json()['error'] == 'Invalid username or password'


def test_unknown_user_gives_the_same_error(client):
    response = client.post('/api/auth/login',
                           json={'username': 'nobody', 'password': 'pw'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid username or password'


def test_availability_reports_taken_names(client):
    body = client.get('/api/users/availability?username=parent&email=free@x.local'
                      ).get_json()
    assert body['username_taken'] is True
    assert body['email_taken'] is False


# ----------------------------------------------------------- registration

def test_register_parent_creates_children_and_plans(client, ids):
    response = client.post('/api/parents', json={
        'username': 'apifamily', 'email': 'apifamily@x.local', 'password': 'pw',
        'firstname': 'Api', 'lastname': 'Family',
        'education_level': 'BACHELORS_DEGREE',
        'preschool_id': ids['preschool'],
        'children': [
            {'username': 'apikid1', 'password': 'pw', 'firstname': 'One',
             'age': 5, 'gender': 'Female', 'lunch_type': 'STANDARD',
             'teacher_id': ids['teacher']},
            {'username': 'apikid2', 'password': 'pw', 'firstname': 'Two',
             'age': 6, 'gender': 'Male', 'lunch_type': 'Free/Reduced',
             'teacher_id': ids['teacher']},
        ],
    })
    assert response.status_code == 201
    body = response.get_json()
    assert len(body['children']) == 2

    from app.models import Child, LearningPlan
    with flask_app.app_context():
        for username in ('apikid1', 'apikid2'):
            child = Child.query.filter_by(username=username).first()
            assert child is not None
            # Children inherit the family name and the parent's education.
            assert child.lastname == 'Family'
            assert child.parent_education.name == 'BACHELORS_DEGREE'
            # A child with no plan can see no content at all.
            assert LearningPlan.query.filter_by(child_id=child.id).first() is not None


def test_register_parent_rejects_a_taken_username_with_409(client, ids):
    response = client.post('/api/parents', json={
        'username': 'parent', 'email': 'other@x.local', 'password': 'pw',
        'firstname': 'Dup', 'lastname': 'Licate',
        'education_level': 'HIGH_SCHOOL',
        'children': [{'username': 'dupkid', 'password': 'pw', 'firstname': 'K',
                      'age': 5, 'gender': 'Other', 'lunch_type': 'STANDARD'}],
    })
    assert response.status_code == 409


def test_a_rejected_registration_writes_nothing(client):
    """The second child is invalid, so the parent and first child must not
    survive either -- one transaction or none."""
    response = client.post('/api/parents', json={
        'username': 'halffamily', 'email': 'half@x.local', 'password': 'pw',
        'firstname': 'Half', 'lastname': 'Family',
        'education_level': 'HIGH_SCHOOL',
        'children': [
            {'username': 'goodkid', 'password': 'pw', 'firstname': 'Good',
             'age': 5, 'gender': 'Other', 'lunch_type': 'STANDARD'},
            {'username': 'badkid', 'password': 'pw', 'firstname': 'Bad',
             'age': 'not-a-number', 'gender': 'Other', 'lunch_type': 'STANDARD'},
        ],
    })
    assert response.status_code == 400

    from app.models import User
    with flask_app.app_context():
        assert User.query.filter_by(username='halffamily').first() is None
        assert User.query.filter_by(username='goodkid').first() is None


def test_register_parent_needs_at_least_one_child(client):
    response = client.post('/api/parents', json={
        'username': 'lonely', 'email': 'lonely@x.local', 'password': 'pw',
        'firstname': 'No', 'lastname': 'Kids',
        'education_level': 'HIGH_SCHOOL', 'children': [],
    })
    assert response.status_code == 400


def test_register_teacher(client, ids):
    response = client.post('/api/teachers', json={
        'username': 'apiteacher', 'email': 'apiteacher@x.local', 'password': 'pw',
        'firstname': 'Api', 'lastname': 'Teacher',
        'preschool_id': ids['preschool'],
    })
    assert response.status_code == 201
    assert response.get_json()['teacher']['username'] == 'apiteacher'


# ------------------------------------------------------------------ users

def test_get_user_embeds_relations(client, ids):
    user = client.get(f"/api/users/{ids['parent']}").get_json()['user']
    assert user['type'] == 'parent'
    assert 'children' in user
    assert user['education_level']['name']


def test_child_payload_carries_the_subclass_fields(client, ids):
    """Templates read current_user.gender and .recommended_level directly."""
    child = client.get(f"/api/children/{ids['child']}").get_json()['child']
    assert child['gender']
    assert child['recommended_level']['name']
    assert child['parent_id'] == ids['parent']


def test_children_filtered_by_parent(client, ids):
    body = client.get(f"/api/children?parent_id={ids['parent']}").get_json()
    assert {c['username'] for c in body['children']} == {'child', 'child2'}


def test_bad_filter_is_400(client):
    assert client.get('/api/children?parent_id=abc').status_code == 400


def test_unknown_user_is_404(client):
    assert client.get('/api/users/999999').status_code == 404


# ------------------------------------------------------------- preschools

def test_preschools_are_listable_without_a_token(client):
    """The signup wizard needs this before an account exists."""
    body = client.get('/api/preschools').get_json()
    assert body['preschools']
    assert 'name' in body['preschools'][0]


def test_preschool_crud_round_trip(client):
    created = client.post('/api/preschools', json={'name': 'API Preschool'})
    assert created.status_code == 201
    school_id = created.get_json()['preschool']['id']

    renamed = client.patch(f'/api/preschools/{school_id}',
                           json={'name': 'API Preschool Renamed'})
    assert renamed.get_json()['preschool']['name'] == 'API Preschool Renamed'

    assert client.delete(f'/api/preschools/{school_id}').status_code == 204
    assert client.get(f'/api/preschools/{school_id}').status_code == 404


def test_occupied_preschool_cannot_be_deleted(client, ids):
    """The seeded preschool has learners, so the service raises Conflict."""
    assert client.delete(f"/api/preschools/{ids['preschool']}").status_code == 409


# ---------------------------------------------------------------- plans

def test_plan_has_all_five_strands_as_ranked_enums(client, ids):
    plan = client.get(
        f"/api/learning-plans/child/{ids['child']}").get_json()['learning_plan']
    for field in ('science_level', 'technology_level', 'engineering_level',
                  'math_level', 'story_level'):
        assert plan[field]['name']
        assert isinstance(plan[field]['rank'], int)


def test_put_plan_replaces_rather_than_duplicates(client, ids):
    """There is exactly one plan per child, enforced by the database."""
    payload = {field: 'INTERMEDIATE' for field in
               ('science_level', 'technology_level', 'engineering_level',
                'math_level', 'story_level')}
    first = client.put(f"/api/learning-plans/child/{ids['child2']}", json=payload)
    second = client.put(f"/api/learning-plans/child/{ids['child2']}", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    from app.models import LearningPlan
    with flask_app.app_context():
        assert LearningPlan.query.filter_by(child_id=ids['child2']).count() == 1


def test_put_plan_rejects_a_bad_level(client, ids):
    payload = {field: 'INTERMEDIATE' for field in
               ('science_level', 'technology_level', 'engineering_level',
                'math_level', 'story_level')}
    payload['math_level'] = 'WIZARD'
    assert client.put(f"/api/learning-plans/child/{ids['child']}",
                      json=payload).status_code == 400


def test_recommendations_split_activities_from_stories(client, ids):
    body = client.get(
        f"/api/learning-plans/child/{ids['child']}/recommendations").get_json()
    assert 'activities' in body and 'stories' in body
    assert all(a['stem_code'] for a in body['activities'])
    # Stories have no STEM strand.
    assert all('stem_code' not in s for s in body['stories'])


# ------------------------------------------------------ progress & results

def test_child_progress_embeds_the_content(client, ids):
    """parent_progress.html reads progress.learning_content.type.value."""
    rows = client.get(f"/api/children/{ids['child']}/progress").get_json()['progress']
    assert rows
    assert rows[0]['learning_content']['title']
    assert rows[0]['learning_content']['type']['value']


def test_teacher_progress_embeds_the_child(client, ids):
    """The extra level a parent does not need: a teacher must see whose row it is."""
    rows = client.get(f"/api/progress?teacher_id={ids['teacher']}").get_json()['progress']
    assert rows
    assert rows[0]['child']['firstname']


def test_progress_index_requires_a_teacher_id(client):
    assert client.get('/api/progress').status_code == 400


def test_results_carry_an_iso_timestamp_with_offset(client, ids):
    """Rule 1: a naive isoformat gives the client no zone. This must not be
    ambiguous."""
    rows = client.get(f"/api/children/{ids['child']}/results").get_json()['results']
    assert rows
    assert rows[0]['date_acquired'].endswith('+00:00')
    assert rows[0]['activity']['stem_code']['name']


def test_stem_levels_cover_every_strand(client, ids):
    """The radar chart needs all four keys present, zero where untried."""
    body = client.get(f"/api/children/{ids['child']}/stem-levels").get_json()
    assert set(body) == {'science', 'technology', 'engineering', 'math'}
    assert all(isinstance(v, (int, float)) for v in body.values())


# ---------------------------------------------------------------- feedback

def test_feedback_round_trip(client, ids):
    sent = client.post('/api/feedback', json={
        'sender_id': ids['teacher'], 'recipient_id': ids['parent'],
        'subject': 'API note', 'content': 'Sent over JSON.',
        'child_id': ids['child'],
    })
    assert sent.status_code == 201
    message_id = sent.get_json()['feedback']['id']

    inbox = client.get(
        f"/api/feedback?recipient_id={ids['parent']}&unread=true").get_json()
    assert any(m['id'] == message_id for m in inbox['feedback'])
    assert inbox['feedback'][0]['sender']['firstname']

    read = client.post(f'/api/feedback/{message_id}/read')
    assert read.get_json()['feedback']['is_read'] is True

    # Out of the inbox, still in the history.
    inbox_after = client.get(
        f"/api/feedback?recipient_id={ids['parent']}&unread=true").get_json()
    assert not any(m['id'] == message_id for m in inbox_after['feedback'])

    history = client.get(
        f"/api/feedback?participant_id={ids['parent']}").get_json()
    assert any(m['id'] == message_id for m in history['feedback'])


def test_feedback_needs_a_subject_and_message(client, ids):
    response = client.post('/api/feedback', json={
        'sender_id': ids['teacher'], 'recipient_id': ids['parent'],
        'subject': '   ', 'content': '',
    })
    assert response.status_code == 400


def test_unscoped_feedback_listing_is_refused(client):
    """An unfiltered listing would return everybody's mail."""
    assert client.get('/api/feedback').status_code == 400


def test_reading_is_a_post_not_a_get(client, ids):
    """A GET that mutates means any preview or crawler marks mail as read."""
    assert client.get(f"/api/feedback/{ids['child']}/read").status_code == 405
