from config import db as default_db
from models.activity import Activity, StemCode
from models.child import Level
from models.learning_plan import LearningPlan
from models.story import Story

# Every field on a learning plan, in the order the forms present them.
PLAN_FIELDS = ('science_level', 'technology_level', 'engineering_level',
               'math_level', 'story_level')


class LearningPlanService:
    def __init__(self, db=None):
        self.db = db or default_db

    def create_learning_plan(self, child_id, science_level, technology_level,
                             engineering_level, math_level, story_level):
        """Create (or replace) a child's learning plan from explicit levels.

        The caller decides where the levels come from -- an ML recommendation or
        a teacher's form. This method no longer re-runs the predictor and throws
        the caller's arguments away.
        """
        levels = {
            'science_level': Level.coerce(science_level, Level.BEGINNER),
            'technology_level': Level.coerce(technology_level, Level.BEGINNER),
            'engineering_level': Level.coerce(engineering_level, Level.BEGINNER),
            'math_level': Level.coerce(math_level, Level.BEGINNER),
            'story_level': Level.coerce(story_level, Level.BEGINNER),
        }

        # A child has exactly one plan (Child.learning_plan is uselist=False), so
        # update in place instead of inserting a second orphaned row.
        learning_plan = self.get_learning_plan_by_child(child_id)
        if learning_plan is None:
            learning_plan = LearningPlan(child_id=child_id, **levels)
            self.db.session.add(learning_plan)
        else:
            for field, level in levels.items():
                setattr(learning_plan, field, level)

        self.db.session.commit()
        return learning_plan

    def get_learning_plan(self, learning_plan_id):
        return self.db.session.get(LearningPlan, learning_plan_id)

    def get_learning_plan_by_child(self, child_id):
        return LearningPlan.query.filter_by(child_id=child_id).first()

    def update_learning_plan_from_recommendation(self, child_id, recommended_level):
        learning_plan = self.get_learning_plan_by_child(child_id)
        if not learning_plan:
            return False

        level = Level.coerce(recommended_level)
        if level is None:
            return False

        for field in PLAN_FIELDS:
            setattr(learning_plan, field, level)
        self.db.session.commit()
        return True

    def update_learning_plan_from_activity(self, child_id, stem_code, score):
        """Move one STEM strand up or down after an activity is submitted."""
        learning_plan = self.get_learning_plan_by_child(child_id)
        if not learning_plan or stem_code is None:
            return None

        # stem_code arrives as a StemCode enum; LearningPlan.get_level knows how
        # to map either an enum or a string onto the right column.
        current_level = learning_plan.get_level(stem_code)
        if current_level is None:
            return None

        # Levels are strings, so step through the ordered list -- never do
        # arithmetic on Level.value.
        if score >= 90:
            new_level = current_level.shifted(1)
        elif score < 60:
            new_level = current_level.shifted(-1)
        else:
            new_level = current_level

        learning_plan.set_level(stem_code, new_level)
        self.db.session.commit()

        return learning_plan

    def update_learning_plan(self, learning_plan_id, science_level, technology_level,
                             engineering_level, math_level, story_level):
        learning_plan = self.get_learning_plan(learning_plan_id)
        if not learning_plan:
            return None

        submitted = (science_level, technology_level, engineering_level,
                     math_level, story_level)
        for field, value in zip(PLAN_FIELDS, submitted, strict=True):
            level = Level.coerce(value, getattr(learning_plan, field))
            if level is None:
                return None
            setattr(learning_plan, field, level)

        self.db.session.commit()
        return learning_plan

    def recommend_activities(self, child_id):
        """Content at or below the child's level for each strand."""
        learning_plan = self.get_learning_plan_by_child(child_id)
        if not learning_plan:
            return []

        recommended = []
        for stem_code in StemCode:
            level = learning_plan.get_level(stem_code)
            if level is None:
                continue
            allowed = [candidate for candidate in Level if candidate.rank <= level.rank]
            recommended.extend(
                Activity.query
                .filter(Activity.stem_code == stem_code, Activity.level.in_(allowed))
                .all()
            )

        if learning_plan.story_level is not None:
            allowed = [c for c in Level if c.rank <= learning_plan.story_level.rank]
            recommended.extend(Story.query.filter(Story.level.in_(allowed)).all())

        # Sort by difficulty. Sorting on level.value would order these
        # alphabetically: ADVANCED, BEGINNER, INTERMEDIATE.
        return sorted(recommended, key=lambda item: (item.level.rank, item.id))
