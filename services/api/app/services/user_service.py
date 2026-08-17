from app.config import db as default_db
from app.models.user import User
from app.services.errors import Conflict, NotFound


class UserService:
    def __init__(self, db=None):
        self.db = db or default_db

    def get_user(self, user_id):
        return self.db.session.get(User, user_id)

    def get_user_by_username(self, username):
        return User.query.filter_by(username=username).first()

    def get_users(self):
        return User.query.order_by(User.id).all()

    def _require(self, user_id):
        user = self.get_user(user_id)
        if user is None:
            raise NotFound("That user no longer exists")
        return user

    def _assert_available(self, user_id, username=None, email=None):
        """Usernames and emails are unique; say which one collided."""
        if username and User.query.filter(User.username == username,
                                          User.id != user_id).first():
            raise Conflict("That username is already taken")
        if email and User.query.filter(User.email == email,
                                       User.id != user_id).first():
            raise Conflict("That email address is already in use")

    def update_user(self, user_id, username=None, email=None):
        user = self._require(user_id)
        self._assert_available(user_id, username, email)
        if username:
            user.username = username
        if email:
            user.email = email
        self.db.session.commit()
        return user

    def delete_user(self, user_id):
        user = self._require(user_id)
        self.db.session.delete(user)
        self.db.session.commit()
        return user

    def update_user_profile(self, user_id, username, email, password=None):
        user = self._require(user_id)
        self._assert_available(
            user_id,
            username if username and username != user.username else None,
            email if email and email != user.email else None,
        )

        if username:
            user.username = username
        if email:
            user.email = email
        if password:
            user.set_password(password)

        self.db.session.commit()
        return user
