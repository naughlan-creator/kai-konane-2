from models.learning_plan import LearningPlan
from models.activity import Activity, StemCode
from models.child import Child, Level
from models.story import Story
from config import db
from level_predictor import update_child_level

class LearningPlanService:
    def __init__(self):
        self.db = db

    def create_learning_plan(self, child_id, science_level, technology_level, engineering_level, math_level, story_level):
        # First, update the child's level using the ML model
        success, recommended_level = update_child_level(child_id)

        if success:
            # Use the recommended level from the ML model
            learning_plan = LearningPlan(
                child_id=child_id,
                science_level=recommended_level,
                technology_level=recommended_level,
                engineering_level=recommended_level,
                math_level=recommended_level,
                story_level=recommended_level
            )
        else:
            # If ML prediction fails, use the levels provided by the teacher
            learning_plan = LearningPlan(
                child_id=child_id,
                science_level=science_level,
                technology_level=technology_level,
                engineering_level=engineering_level,
                math_level=math_level,
                story_level=story_level
            )

        db.session.add(learning_plan)
        db.session.commit()
        return learning_plan

    def get_learning_plan(self, learning_plan_id):
        return LearningPlan.query.get(learning_plan_id)

    def get_learning_plan_by_child(self, child_id):
        return LearningPlan.query.filter_by(child_id=child_id).first()

    def update_learning_plan_from_recommendation(self, child_id, recommended_level):
        learning_plan = self.get_learning_plan_by_child(child_id)
        if learning_plan:
            learning_plan.science_level = recommended_level
            learning_plan.technology_level = recommended_level
            learning_plan.engineering_level = recommended_level
            learning_plan.math_level = recommended_level
            learning_plan.story_level = recommended_level
            db.session.commit()
        return learning_plan
    
    def update_learning_plan_from_activity(self, child_id, stem_code, score):
        learning_plan = self.get_learning_plan_by_child(child_id)
        if not learning_plan:
            return None

        current_level = getattr(learning_plan, f"{stem_code.lower()}_level")
        
        if score >= 90 and current_level != Level.ADVANCED:
            new_level = Level(min(current_level.value + 1, Level.ADVANCED.value))
        elif score < 60 and current_level != Level.BEGINNER:
            new_level = Level(max(current_level.value - 1, Level.BEGINNER.value))
        else:
            new_level = current_level

        setattr(learning_plan, f"{stem_code.lower()}_level", new_level)
        db.session.commit()

        return learning_plan
    
    def update_learning_plan(self, learning_plan_id, science_level, technology_level, engineering_level, math_level, story_level):
        learning_plan = LearningPlan.query.get(learning_plan_id)
        if learning_plan:
            learning_plan.science_level = Level[science_level.upper()]
            learning_plan.technology_level = Level[technology_level.upper()]
            learning_plan.engineering_level = Level[engineering_level.upper()]
            learning_plan.math_level = Level[math_level.upper()]
            learning_plan.story_level = Level[story_level.upper()]
            db.session.commit()
            return learning_plan
        return None

    def delete_learning_plan(self, learning_plan_id):
        learning_plan = self.get_learning_plan(learning_plan_id)
        if learning_plan:
            self.db.session.delete(learning_plan)
            self.db.session.commit()
            return True
        return False

    def recommend_activities(self, child_id):
        learning_plan = self.get_learning_plan_by_child(child_id)
        if not learning_plan:
            return []

        recommended_activities = []
        for stem_code in StemCode:
            level = getattr(learning_plan, f"{stem_code.name.lower()}_level")
            activities = Activity.query.filter_by(stem_code=stem_code, level=level).order_by(Activity.id).all()
            recommended_activities.extend(activities)

        # Add story recommendations
        stories = Story.query.filter_by(level=learning_plan.story_level).order_by(Story.id).all()
        recommended_activities.extend(stories)

        return sorted(recommended_activities, key=lambda x: (x.level.value, x.id))