from flask import Blueprint, render_template
from flask_login import login_required

learning_content_bp = Blueprint('learning_content', __name__)

@learning_content_bp.route('/learning-content')
@login_required
def learning_content():
    return render_template('ContentManagement/learning_content.html')
