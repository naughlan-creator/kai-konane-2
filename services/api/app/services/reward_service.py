from app.config import db as default_db
from app.models.reward import Reward
from app.utils import utcdate

# Score thresholds, best first. Ordering matters: the first match wins.
BADGES = ((90, "Gold Star"), (75, "Silver Star"), (60, "Bronze Star"))
PARTICIPATION = "Participation Badge"


class RewardService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_reward(self, child_id, content, activity_id=None, story_id=None):
        reward = Reward(
            child_id=child_id,
            content=content,
            activity_id=activity_id,
            story_id=story_id,
            date_acquired=utcdate(),
        )
        self.db.session.add(reward)
        self.db.session.commit()
        return reward

    def create_reward_for_activity(self, child_id, activity_id, score):
        content = next((badge for threshold, badge in BADGES if score >= threshold),
                       PARTICIPATION)

        # One badge of each grade per activity: retrying should not print a
        # fresh sticker every time.
        reward = Reward.query.filter_by(child_id=child_id, activity_id=activity_id,
                                        content=content).first()
        if reward is None:
            reward = self.add_reward(child_id=child_id, content=content,
                                     activity_id=activity_id)
        return reward, f"You earned a {content}!"
