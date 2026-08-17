from app.routes.activity_routes import activity_bp
from app.routes.admin_routes import admin_bp
from app.routes.feedback_routes import feedback_bp
from app.routes.learning_content_routes import learning_content_bp
from app.routes.learning_plan_routes import learning_plan_bp
from app.routes.preschool_routes import preschool_bp
from app.routes.profile_routes import profile_bp
from app.routes.progress_route import progress_bp
from app.routes.story_routes import story_bp
from app.routes.user_routes import user_bp

__all__ = [
    'activity_bp',
    'admin_bp',
    'feedback_bp',
    'learning_content_bp',
    'learning_plan_bp',
    'preschool_bp',
    'profile_bp',
    'progress_bp',
    'story_bp',
    'user_bp',
]
