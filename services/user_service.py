from models.user import User
from werkzeug.security import generate_password_hash
from config import db as default_db

class UserService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_user(self, user):
        self.db.session.add(user)
        self.db.session.commit()
        if self.get_user(user.id):
            return "User added!!!"
        return "User not added!!!"

    def get_user(self, user_id):
        return self.db.session.get(User, user_id)

    def get_user_by_username(self, username):
        return User.query.filter_by(username=username).first()

    def get_users(self):
        return User.query.all()

    def update_user(self, user_id, username=None, email=None):
        existing_user = self.get_user(user_id)
        if not existing_user:
            return "User not updated!!!"
        if username:
            existing_user.username = username
        if email:
            existing_user.email = email
        self.db.session.commit()
        return "User updated!!!"

    def delete_user(self, user_id):
        user = self.get_user(user_id)
        if user:
            self.db.session.delete(user)
            self.db.session.commit()
            return "User deleted!!!"
        return "User not deleted!!!"

    def update_user_profile(self, user_id, username, email, password=None):
        user = self.get_user(user_id)
        if not user:
            return "User not found"

        if username and username != user.username:
            if User.query.filter(User.username == username, User.id != user_id).first():
                return "That username is already taken"
            user.username = username
        if email and email != user.email:
            if User.query.filter(User.email == email, User.id != user_id).first():
                return "That email is already in use"
            user.email = email
        if password:
            user.password = generate_password_hash(password)

        self.db.session.commit()
        return "Profile updated successfully"
