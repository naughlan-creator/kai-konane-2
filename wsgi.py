from app import app, create_admin, db

with app.app_context():
    db.create_all()
    create_admin()

if __name__ == "__main__":
    app.run()