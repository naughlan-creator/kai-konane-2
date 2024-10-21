from models.user import User
from werkzeug.security import generate_password_hash

class UserService:
    def __init__(self, db):
        self.db = db

    def add_user(self, user):
        self.db.session.add(user)
        self.db.session.commit()
        if self.get_user(user.id):
            return "User added!!!"
        return "User not added!!!"

    def get_user(self, user_id):
        return User.query.get(user_id)

    def get_user_by_username(self, username):
        return User.query.filter_by(username=username).first()

    def get_users():
        return User.query.all()

    def update_user(self, user):
        existing_user = self.get_user_by_username(user.username)
        if existing_user:
            existing_user.name = user.name
            self.db.session.commit()
            return "User updated!!!"
        return "User not updated!!!"

    def delete_user(self, user_id):
        user = self.get_user(user_id)
        if user:
            self.db.session.delete(user)
            self.db.session.commit()
            return "User deleted!!!"
        return "User not deleted!!!"
    
    def update_user_profile(self, user_id, username, email, password=None):
        user = self.get_user(user_id)
        if user:
            user.username = username
            user.email = email
            if password:
                user.password = generate_password_hash(password)  # In a real app, you'd hash the password here
            self.db.session.commit()
            return "Profile updated successfully"
        return "User not found"