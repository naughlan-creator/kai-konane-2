from flask import Blueprint, render_template

from app.routes.auth import child_required

learning_content_bp = Blueprint('learning_content', __name__)

# The template is the learner's content hub and reads current_user.gender, which
# only a Child has -- so this page must be limited to children.
@learning_content_bp.route('/learning-content')
@child_required
def learning_content():
    return render_template('ContentManagement/learning_content.html')
