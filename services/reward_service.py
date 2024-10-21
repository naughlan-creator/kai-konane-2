from models.reward import Reward
from config import db
from datetime import datetime

class RewardService:
    def __init__(self):
        self.db = db

    def add_reward(self, child_id, activity_id, content):
        reward = Reward(child_id, activity_id, content)
        self.db.session.add(reward)
        self.db.session.commit()
        return reward

    def create_reward_for_activity(self, child_id, activity_id, score):
        # Define reward thresholds
        if score >= 90:
            content = "Gold Star"
        elif score >= 75:
            content = "Silver Star"
        elif score >= 60:
            content = "Bronze Star"
        else:
            content = "Participation Badge"

        # Create and save the reward
        reward = Reward(
            child_id=child_id,
            activity_id=activity_id,
            content=content,
            dateAquired=datetime.utcnow()
        )
        db.session.add(reward)
        db.session.commit()

        return reward, f"You earned a {content}!"

    def get_reward(self, reward_id):
        return Reward.query.get(reward_id)
    
    def get_rewards_by_child(self, child_id):
        return Reward.query.filter_by(child_id=child_id).all()
    
    def get_rewards_by_activity(self, activity_id):
        return Reward.query.filter_by(activity_id=activity_id).all()

    def get_rewards():
        return Reward.query.all()

    def update_reward(self, reward_id, new_content):
        reward = self.get_reward(reward_id)
        if reward:
            reward.content = new_content
            self.db.session.commit()
            return "Reward updated!!!"
        return "Reward not updated!!!"

    def delete_reward(self, reward_id):
        reward = self.get_reward(reward_id)
        if reward:
            self.db.session.delete(reward)
            self.db.session.commit()
            return "Reward deleted!!!"
        return "Reward not deleted!!!"