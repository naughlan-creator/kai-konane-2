"""Fixtures for the web service.

`web` is tested with the api stubbed out, not running. That is the point of the
split: this service's job is to turn JSON into HTML and enforce role guards, and
it should be testable without a database, a network or a second process.

The trade is that these fixtures can drift from the real api's responses. The
api's own contract tests are what keep the payload shapes honest; these keep the
templates honest about consuming them.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "web-test-only")

from app import api_client, create_app  # noqa: E402

flask_app = create_app({"TESTING": True, "SECRET_KEY": "web-test-only"})


def _user(uid, username, role, **extra):
    payload = {
        'id': uid, 'username': username, 'email': f'{username}@x.local',
        'role': {'name': role, 'value': role}, 'type': role.lower(),
        'display_name': username.title(), 'firstname': username.title(),
        'lastname': 'Rewi',
    }
    payload.update(extra)
    return payload


# Names mirror the api's demo seed, so a failure here reads the same way as a
# failure against a real database.
CHILD = _user(4, 'child', 'CHILD', firstname='Ari', age=5, gender='Female',
              parent_id=3, teacher_id=2,
              recommended_level={'name': 'BEGINNER', 'value': 'BEGINNER', 'rank': 0})
CHILD2 = _user(5, 'child2', 'CHILD', firstname='Nikau', age=6, gender='Male',
               parent_id=3, teacher_id=2,
               recommended_level={'name': 'BEGINNER', 'value': 'BEGINNER', 'rank': 0})
PARENT = _user(3, 'parent', 'PARENT', firstname='Pania',
               children=[CHILD, CHILD2],
               education_level={'name': 'HIGH_SCHOOL', 'value': 'high school'})
TEACHER = _user(2, 'teacher', 'TEACHER', firstname='Tina',
                lastname='Kahu', students=[CHILD, CHILD2])
ADMIN = _user(1, 'admin', 'ADMIN', name='Site Administrator')

USERS = {u['username']: u for u in (PARENT, TEACHER, CHILD, CHILD2, ADMIN)}
BY_ID = {u['id']: u for u in (PARENT, TEACHER, CHILD, CHILD2, ADMIN)}

LEVEL = {'name': 'BEGINNER', 'value': 'BEGINNER', 'rank': 0}
PLAN = {'id': 1, 'child_id': 4, 'science_level': LEVEL, 'technology_level': LEVEL,
        'engineering_level': LEVEL, 'math_level': LEVEL, 'story_level': LEVEL}

ACTIVITY = {
    'id': 1, 'title': 'Counting to Ten', 'description': 'Count things.',
    'type': {'name': 'ACTIVITY', 'value': 'Activity'},
    'stem_code': {'name': 'MATH', 'value': 'MATH'},
    'level': LEVEL, 'cover_image': 'Basic_counting.jpeg', 'question_count': 2,
    'questions': [{'id': 1, 'content': 'How many?', 'position': 1,
                   'answers': [{'id': 1, 'content': 'Two', 'position': 1,
                                'is_correct': True}]}],
    'progress': {'id': 1, 'completion_rate': 100.0, 'completed': True,
                 'total_num_questions': 2, 'child_id': 4,
                 'learning_content_id': 1},
}

STORY = {
    'id': 2, 'title': "Ben the Bear's Big Adventure", 'description': 'A bear.',
    'type': {'name': 'STORY', 'value': 'Story'}, 'level': LEVEL,
    'cover_page': 'BB_cover_page.png', 'page_count': 1,
    'pages': [{'id': 1, 'line_of_page': 'Ben woke up.',
               'image_filename': 'BB_page_1.png', 'page_number': 1,
               'is_last_page': True}],
    'progress': None,
}

FEEDBACK = {
    'id': 1, 'subject': 'Great week', 'message': 'Ari did well.',
    'sender_id': 2, 'recipient_id': 3, 'child_id': 4,
    'sent_at': '2026-08-17T12:10:28+00:00', 'is_read': False,
    'sender': {'id': 2, 'firstname': 'Tina', 'lastname': 'Kahu'},
}

PROGRESS_ROW = {
    'id': 1, 'completion_rate': 100.0, 'total_num_questions': 2,
    'completed': True, 'child_id': 4, 'learning_content_id': 1,
    'learning_content': {'id': 1, 'title': 'Counting to Ten',
                         'type': {'name': 'ACTIVITY', 'value': 'Activity'}},
    'child': {'id': 4, 'firstname': 'Ari', 'lastname': 'Rewi'},
}

RESULT_ROW = {
    'id': 1, 'child_id': 4, 'activity_id': 1, 'score': 100.0,
    'date_acquired': '2026-08-17T12:10:28+00:00',
    'activity': {'id': 1, 'title': 'Counting to Ten',
                 'stem_code': {'name': 'MATH', 'value': 'MATH'}},
    'child': {'id': 4, 'firstname': 'Ari', 'lastname': 'Rewi'},
}

ENUMS = {
    'EducationLevel': [{'name': 'HIGH_SCHOOL', 'value': 'high school'}],
    'LunchType': [{'name': 'STANDARD', 'value': 'Standard'}],
    'Level': [LEVEL],
    'StemCode': [{'name': 'MATH', 'value': 'MATH'}],
    'Role': [{'name': r, 'value': r}
             for r in ('ADMIN', 'CHILD', 'PARENT', 'TEACHER')],
}


def fake_request(method, path, *, json=None, params=None, token=None,
                 headers=None):
    """Stand in for the api. Raises ApiNotFound for anything unmapped, which is
    what the real client does and what the routes are written to expect."""
    params = params or {}
    path = path.strip('/')

    if path == 'auth/login':
        user = USERS.get((json or {}).get('username'))
        if user is None or (json or {}).get('password') != 'pw':
            raise api_client.ApiUnauthorized('Invalid username or password')
        return {'user': user, 'token': f"tok-{user['id']}", 'expires_in': 43200}

    if path.startswith('users/availability'):
        return {'username_taken': False, 'email_taken': False}
    if path == 'users':
        return {'users': list(BY_ID.values())}
    if path.startswith('users/'):
        user = BY_ID.get(int(path.split('/')[1]))
        if user is None:
            raise api_client.ApiNotFound('No such user')
        return {'user': user}

    if path == 'enums':
        return ENUMS
    if path == 'preschools':
        return {'preschools': [{'id': 1, 'name': 'Kai Konane Preschool'}]}
    if path.startswith('preschools/'):
        return {'preschool': {'id': 1, 'name': 'Kai Konane Preschool',
                              'students': [CHILD], 'teachers': [TEACHER]}}
    if path == 'teachers':
        return {'teachers': [TEACHER]}
    if path.endswith('/students'):
        return {'students': [CHILD, CHILD2]}
    if path.endswith('/children'):
        return {'children': [CHILD, CHILD2]}

    if path == 'children':
        return {'children': [CHILD, CHILD2]}
    if path.endswith('/progress') and path.startswith('children/'):
        return {'progress': [PROGRESS_ROW]}
    if path.endswith('/results') and path.startswith('children/'):
        return {'results': [RESULT_ROW]}
    if path.endswith('/stem-levels'):
        return {'science': 0, 'technology': 0, 'engineering': 0, 'math': 100.0}
    if path.startswith('children/'):
        return {'child': CHILD}

    if path == 'progress':
        return {'progress': [PROGRESS_ROW]}
    if path == 'results':
        return {'results': [RESULT_ROW]}

    if path.endswith('/recommendations'):
        return {'activities': [ACTIVITY], 'stories': [STORY]}
    if path.startswith('learning-plans/'):
        return {'learning_plan': PLAN}

    if path == 'activities':
        return {'activities': [ACTIVITY]} if method == 'GET' else {'activity': ACTIVITY}
    if path.startswith('activities/'):
        return {'activity': ACTIVITY}
    if path == 'stories':
        return {'stories': [STORY]} if method == 'GET' else {'story': STORY}
    if path.startswith('stories/'):
        return {'story': STORY}

    if path == 'feedback':
        return {'feedback': [FEEDBACK]} if method == 'GET' else {'feedback': FEEDBACK}
    if path.startswith('feedback/'):
        return {'feedback': FEEDBACK}

    if path == 'media':
        return {'images': ['logo.svg', 'Basic_counting.jpeg']}

    raise api_client.ApiNotFound(f'No stub for {method} {path}')


@pytest.fixture(autouse=True)
def stub_api(monkeypatch):
    """Every test runs against the stub. No test may reach a real network."""
    def bind(method):
        # A closure per verb: a lambda reading the loop variable would leave
        # every function bound to the last one.
        def call(path, **kwargs):
            return fake_request(method, path, **kwargs)
        return call

    monkeypatch.setattr(api_client, 'request', fake_request)
    for name in ('get', 'post', 'patch', 'put', 'delete'):
        monkeypatch.setattr(api_client, name, bind(name.upper()))
    return fake_request


@pytest.fixture()
def app():
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username):
    return client.post('/users/login',
                       data={'username': username, 'password': 'pw'})
