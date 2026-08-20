"""Creating, editing and deleting content over JSON.

These endpoints are what the admin authoring forms in `web` post to. The
question and page sync is the interesting part: a row carrying an id is edited,
one without is new, and getting that wrong duplicates the whole set on every
save.
"""
import io

ACTIVITY = {
    'title': 'Counting Shapes',
    'stem_code': 'MATH',
    'level': 'BEGINNER',
    'description': 'Count the shapes.',
    'questions': [
        {'content': 'How many circles?',
         'answers': [{'content': 'Two', 'is_correct': True},
                     {'content': 'Five', 'is_correct': False}]},
        {'content': 'How many squares?',
         'answers': [{'content': 'One', 'is_correct': True},
                     {'content': 'Nine', 'is_correct': False}]},
    ],
}

STORY = {
    'title': 'The Quiet Kea',
    'level': 'BEGINNER',
    'description': 'A bird who whispers.',
    'pages': [
        {'line_of_page': 'Once there was a kea.'},
        {'line_of_page': 'The kea was quiet.'},
    ],
}


# ------------------------------------------------------------- activities

def test_create_activity_with_questions(client):
    response = client.post('/api/activities', json=ACTIVITY)
    assert response.status_code == 201
    activity = response.get_json()['activity']

    assert activity['title'] == 'Counting Shapes'
    assert activity['stem_code']['name'] == 'MATH'
    assert len(activity['questions']) == 2
    assert activity['question_count'] == 2
    # Exactly one correct answer per question, or scoring is undefined.
    for question in activity['questions']:
        assert sum(a['is_correct'] for a in question['answers']) == 1


def test_update_activity_does_not_duplicate_questions(client):
    """The trap: a question sent without its id reads as new, so every save
    doubles the question set."""
    created = client.post('/api/activities', json=dict(
        ACTIVITY, title='Sync Check')).get_json()['activity']

    payload = dict(ACTIVITY, title='Sync Check Renamed', questions=[
        {'id': q['id'], 'content': q['content'] + ' (edited)',
         'answers': [{'id': a['id'], 'content': a['content'],
                      'is_correct': a['is_correct']} for a in q['answers']]}
        for q in created['questions']
    ])
    updated = client.patch(f"/api/activities/{created['id']}",
                           json=payload).get_json()['activity']

    assert updated['title'] == 'Sync Check Renamed'
    assert len(updated['questions']) == 2
    assert updated['questions'][0]['content'].endswith('(edited)')


def test_delete_activity_returns_the_title(client):
    """The caller flashes 'Deleted X' and cannot read a title from a 204."""
    created = client.post('/api/activities', json=dict(
        ACTIVITY, title='Doomed Activity')).get_json()['activity']

    response = client.delete(f"/api/activities/{created['id']}")
    assert response.status_code == 200
    assert response.get_json()['deleted']['title'] == 'Doomed Activity'
    assert client.get(f"/api/activities/{created['id']}").status_code == 404


def test_activity_needs_a_valid_level(client):
    assert client.post('/api/activities',
                       json=dict(ACTIVITY, level='WIZARD')).status_code == 400


def test_activity_needs_a_title(client):
    assert client.post('/api/activities',
                       json=dict(ACTIVITY, title='  ')).status_code == 400


# ---------------------------------------------------------------- stories

def test_create_story_numbers_its_pages(client):
    response = client.post('/api/stories', json=STORY)
    assert response.status_code == 201
    story = response.get_json()['story']

    assert story['page_count'] == 2
    assert [p['page_number'] for p in story['pages']] == [1, 2]
    # The reader needs to know where to stop.
    assert story['pages'][-1]['is_last_page'] is True
    assert story['pages'][0]['is_last_page'] is False


def test_update_story_renumbers_after_a_removal(client):
    created = client.post('/api/stories', json=dict(
        STORY, title='Renumber Me', pages=[
            {'line_of_page': 'One'},
            {'line_of_page': 'Two'},
            {'line_of_page': 'Three'},
        ])).get_json()['story']

    keep = [created['pages'][0], created['pages'][2]]
    updated = client.patch(f"/api/stories/{created['id']}", json=dict(
        STORY, title='Renumber Me', pages=[
            {'id': p['id'], 'line_of_page': p['line_of_page']} for p in keep
        ])).get_json()['story']

    assert updated['page_count'] == 2
    # Contiguous from 1 -- a gap would break the page-forward navigation.
    assert [p['page_number'] for p in updated['pages']] == [1, 2]
    assert updated['pages'][-1]['is_last_page'] is True


def test_delete_story(client):
    created = client.post('/api/stories', json=dict(
        STORY, title='Doomed Story')).get_json()['story']
    response = client.delete(f"/api/stories/{created['id']}")
    assert response.get_json()['deleted']['title'] == 'Doomed Story'
    assert client.get(f"/api/stories/{created['id']}").status_code == 404


def test_story_needs_at_least_one_page(client):
    assert client.post('/api/stories',
                       json=dict(STORY, pages=[])).status_code == 400


# ------------------------------------------------------------------ media

def test_upload_returns_a_filename(client):
    # A one-pixel PNG is enough; the endpoint checks the extension, not pixels.
    png = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
    response = client.post('/api/media',
                           data={'image': (png, 'kea.png')},
                           content_type='multipart/form-data')
    assert response.status_code == 201
    assert response.get_json()['filename'] == 'kea.png'


def test_upload_rejects_a_non_image(client):
    payload = io.BytesIO(b'#!/bin/sh\necho hi\n')
    response = client.post('/api/media',
                           data={'image': (payload, 'evil.sh')},
                           content_type='multipart/form-data')
    assert response.status_code == 400


def test_upload_with_no_file_is_rejected(client):
    assert client.post('/api/media', data={},
                       content_type='multipart/form-data').status_code == 400


def test_library_lists_uploaded_images(client):
    png = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
    client.post('/api/media', data={'image': (png, 'listed.png')},
                content_type='multipart/form-data')
    assert 'listed.png' in client.get('/api/media').get_json()['images']


def test_images_are_served_without_a_token(anon_client):
    """An <img> tag sends no Authorization header, so this must stay public."""
    assert anon_client.get('/api/media/logo.svg').status_code == 200


def test_media_path_traversal_is_refused(anon_client):
    assert anon_client.get('/api/media/../config.py').status_code == 404
