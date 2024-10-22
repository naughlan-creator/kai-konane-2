from flask import render_template
from werkzeug.security import generate_password_hash
from routes import *
from config import app, db
from services import *
from models import *
import os

@app.cli.command("create-admin")
def create_admin():
    with app.app_context():
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists.")
        else:
            admin = Admin(
                username='admin',
                password=generate_password_hash(os.environ.get('ADMIN_PASSWORD', '1234')),
                email=os.environ.get('ADMIN_EMAIL', 'admin@example.com'),
                name='Admin',
                role=Role.ADMIN
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully.")

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database tables created.")

@app.cli.command("reset-db")
def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database has been reset.")

app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(preschool_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(activity_bp)
app.register_blueprint(story_bp)
app.register_blueprint(learning_content_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(learning_plan_bp)
app.register_blueprint(progress_bp)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    create_admin()
    app.run(debug=True)