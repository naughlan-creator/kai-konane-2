"""The JSON content API: shape, filtering and the serialization rules.

These assert on the *contract* — the keys and types web will depend on — not
just on 200s. A response that returns the right status with the wrong shape is
the failure mode that costs a day in #9.
"""
from conftest import flask_app


def test_levels_are_ordered_and_ranked(client):
    body = client.get('/api/levels').get_json()
    assert [item['name'] for item in body['levels']] == [
        'BEGINNER', 'INTERMEDIATE', 'ADVANCED']
    assert [item['rank'] for item in body['levels']] == [0, 1, 2]


def test_enums_serialize_as_objects_with_rank(client, ids):
    """Rule 2: templates read .name and .value; rank carries the ordering that
    .value cannot, because ADVANCED sorts before BEGINNER alphabetically."""
    activity = client.get(f"/api/activities/{ids['activity']}").get_json()['activity']

    assert activity['level'] == {'name': 'BEGINNER', 'value': 'BEGINNER', 'rank': 0}
    # StemCode is unordered, so it carries no rank.
    assert activity['stem_code'] == {'name': 'MATH', 'value': 'MATH'}
    assert 'rank' not in activity['stem_code']


def test_activity_detail_embeds_questions_and_answers(client, ids):
    """Rule 3: activity_detail.html and activity_page.html both traverse
    activity.questions[].answers[], so the detail endpoint must embed both."""
    activity = client.get(f"/api/activities/{ids['activity']}").get_json()['activity']

    assert activity['question_count'] == 3
    assert len(activity['questions']) == 3
    first = activity['questions'][0]
    assert len(first['answers']) >= 2
    assert sum(1 for a in first['answers'] if a['is_correct']) == 1
    # Explicit ordering, not primary-key order.
    assert [q['position'] for q in activity['questions']] == [1, 2, 3]


def test_activity_list_omits_questions(client):
    """The listing must not pay for the detail depth."""
    activities = client.get('/api/activities').get_json()['activities']
    assert activities, "expected seeded activities"
    assert all('questions' not in a for a in activities)
    assert all('question_count' in a for a in activities)


def test_activities_are_beginner_first(client):
    activities = client.get('/api/activities').get_json()['activities']
    ranks = [a['level']['rank'] for a in activities]
    assert ranks == sorted(ranks)


def test_activities_are_filtered_to_the_childs_plan(client, ids):
    """Every activity returned is at or below the child's level for its own strand.

    Asserted against the plan as it currently stands rather than against a
    count: submitting an activity promotes a strand, so any test that hard-codes
    "the beginner child sees 4" breaks the moment another test file scores
    something. Invariants survive shared state; totals do not.
    """
    from app.models.activity import StemCode
    from app.services.learning_plan_service import LearningPlanService

    with flask_app.app_context():
        plan = LearningPlanService().get_learning_plan_by_child(ids['child'])
        ceiling = {strand.name: plan.get_level(strand).rank for strand in StemCode}

    activities = client.get(
        f"/api/activities?child_id={ids['child']}").get_json()['activities']

    assert activities, "expected the child to see some activities"
    for item in activities:
        strand = item['stem_code']['name']
        assert item['level']['rank'] <= ceiling[strand], (
            f"{item['title']} is {item['level']['name']} but the child's "
            f"{strand} level only reaches rank {ceiling[strand]}")


def test_a_higher_level_child_sees_at_least_as_much(client, ids):
    """Monotonicity: raising a level can only widen what is visible."""
    beginner = client.get(f"/api/activities?child_id={ids['child']}").get_json()
    intermediate = client.get(f"/api/activities?child_id={ids['child2']}").get_json()
    assert len(intermediate['activities']) >= len(beginner['activities'])


def test_activity_list_attaches_progress_for_a_child(client, ids):
    activities = client.get(f"/api/activities?child_id={ids['child']}").get_json()
    counting = next(a for a in activities['activities'] if a['title'] == 'Counting to Ten')
    assert counting['progress']['completed'] is True


def test_story_detail_embeds_pages_in_order(client, ids):
    story = client.get(f"/api/stories/{ids['story']}").get_json()['story']
    assert story['page_count'] == len(story['pages'])
    assert [p['page_number'] for p in story['pages']] == list(
        range(1, len(story['pages']) + 1))
    assert story['pages'][-1]['is_last_page'] is True
    assert story['pages'][0]['is_last_page'] is False


def test_stories_are_filtered_to_the_reading_level(client, ids):
    from app.services.learning_plan_service import LearningPlanService

    with flask_app.app_context():
        plan = LearningPlanService().get_learning_plan_by_child(ids['child'])
        ceiling = plan.story_level.rank

    stories = client.get(
        f"/api/stories?child_id={ids['child']}").get_json()['stories']

    assert stories, "expected the child to see some stories"
    assert all(s['level']['rank'] <= ceiling for s in stories)


def test_submit_scores_and_logs_an_attempt(client, ids):
    from app.models import Activity

    with flask_app.app_context():
        activity = flask_app.extensions['sqlalchemy'].session.get(
            Activity, ids['activity'])
        correct = {str(q.id): str(q.correct_answer.id) for q in activity.questions}

    response = client.post(f"/api/activities/{ids['activity']}/submit",
                           json={'child_id': ids['child'], 'answers': correct})
    assert response.status_code == 201
    assert response.get_json()['score'] == 100


def test_completing_a_story_is_idempotent(client, ids):
    """Re-reading must not hand out a second badge."""
    first = client.post(f"/api/stories/{ids['story']}/complete",
                        json={'child_id': ids['child2']})
    second = client.post(f"/api/stories/{ids['story']}/complete",
                         json={'child_id': ids['child2']})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()['reward'] == second.get_json()['reward']

    from app.models import Reward
    with flask_app.app_context():
        assert Reward.query.filter_by(child_id=ids['child2'],
                                      story_id=ids['story']).count() == 1


# ------------------------------------------------------------------ errors

def test_unknown_activity_is_404_json(client):
    response = client.get('/api/activities/999999')
    assert response.status_code == 404
    assert 'error' in response.get_json()


def test_unknown_api_path_returns_json_not_html(client):
    """Flask's default 404 is an HTML page, which would break a JSON client."""
    response = client.get('/api/nope')
    assert response.status_code == 404
    assert response.get_json()['error']


def test_bad_child_id_is_400_not_500(client):
    response = client.get('/api/activities?child_id=abc')
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_submit_without_child_id_is_400(client, ids):
    response = client.post(f"/api/activities/{ids['activity']}/submit",
                           json={'answers': {}})
    assert response.status_code == 400


def test_child_without_a_plan_is_404(client, ids):
    response = client.get(f"/api/activities?child_id={ids['outsider_child']}")
    assert response.status_code == 404
