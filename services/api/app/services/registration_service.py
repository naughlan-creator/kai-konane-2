"""Account creation.

The signup wizards in `web` accumulate form state across several screens and
write nothing until the last one. That final write is the interesting part: a
parent, N children and N learning plans in a single transaction, with the
child's starting level predicted per child.

Extracted from routes so the api can expose it as one endpoint. The wizard stays
presentation; the transaction is domain.
"""
from app.config import db as default_db
from app.level_predictor import predict_child_level
from app.models.child import Child, EducationLevel, Level, LunchType
from app.models.learning_plan import LearningPlan
from app.models.parent import Parent
from app.models.teacher import Teacher
from app.models.user import Role, User
from app.services.errors import Conflict, ValidationError


class RegistrationService:
    def __init__(self, db=None):
        self.db = db or default_db

    # ------------------------------------------------------------- helpers

    @staticmethod
    def availability(username=None, email=None):
        """Whether a username and email are free.

        Advisory only. Between this check and the write someone else can take
        the name, so `register_parent` re-checks inside the transaction and
        raises Conflict. This exists so a four-screen wizard can fail on screen
        two instead of screen four.
        """
        return {
            'username_taken': bool(username) and bool(
                User.query.filter_by(username=username).first()),
            'email_taken': bool(email) and bool(
                User.query.filter_by(email=email).first()),
        }

    def _require_free(self, username, email=None):
        if User.query.filter_by(username=username).first():
            raise Conflict(f"Username '{username}' is already taken")
        if email and User.query.filter_by(email=email).first():
            raise Conflict("That email address is already registered")

    # ------------------------------------------------------------- parents

    def register_parent(self, *, username, email, password, firstname, lastname,
                        education_level, children, preschool_id=None):
        """Create a parent with their children and each child's learning plan.

        One transaction: a half-registered family with no learning plans would
        leave children who can see no content at all.
        """
        if not (username or '').strip():
            raise ValidationError("A username is required")
        if not password:
            raise ValidationError("A password is required")
        if not (firstname or '').strip() or not (lastname or '').strip():
            raise ValidationError("First and last name are required")

        level = EducationLevel.coerce(education_level)
        if level is None:
            raise ValidationError("Choose a valid education level")

        if not children:
            raise ValidationError("Register at least one child")

        cleaned = [self._clean_child(spec, index)
                   for index, spec in enumerate(children, start=1)]

        seen = set()
        for spec in cleaned:
            if spec['username'] in seen:
                raise ValidationError(
                    f"Duplicate username '{spec['username']}' in this registration")
            seen.add(spec['username'])

        self._require_free(username, email)
        for spec in cleaned:
            self._require_free(spec['username'])

        try:
            parent = Parent(
                username=username.strip(),
                email=email,
                firstname=firstname.strip(),
                lastname=lastname.strip(),
                role=Role.PARENT,
                education_level=level,
            )
            parent.set_password(password)
            self.db.session.add(parent)
            self.db.session.flush()

            created = []
            for spec in cleaned:
                child = Child(
                    username=spec['username'],
                    email=f"{spec['username']}@kaikonane.local",
                    role=Role.CHILD,
                    firstname=spec['firstname'],
                    # Children inherit the family name and the parent's
                    # education level; the level model reads the latter.
                    lastname=parent.lastname,
                    age=spec['age'],
                    gender=spec['gender'],
                    parent_id=parent.id,
                    teacher_id=spec['teacher_id'],
                    preschool_id=preschool_id,
                    race_ethnicity=spec['race_ethnicity'],
                    lunch_type=spec['lunch_type'],
                    parent_education=parent.education_level,
                )
                child.set_password(spec['password'])
                self.db.session.add(child)
                self.db.session.flush()

                # predict_child_level returns a Level, or None when the model
                # cannot load -- in which case everyone starts at BEGINNER.
                recommended = predict_child_level(child.id) or Level.BEGINNER
                child.recommended_level = recommended
                self.db.session.add(LearningPlan(
                    child_id=child.id,
                    science_level=recommended,
                    technology_level=recommended,
                    engineering_level=recommended,
                    math_level=recommended,
                    story_level=recommended,
                ))
                created.append(child)

            self.db.session.commit()
            return parent, created
        except Exception:
            self.db.session.rollback()
            raise

    @staticmethod
    def _clean_child(spec, index):
        username = (spec.get('username') or '').strip()
        if not username:
            raise ValidationError(f"Child {index} needs a username")
        if not spec.get('password'):
            raise ValidationError(f"Child {index} needs a password")
        if not (spec.get('firstname') or '').strip():
            raise ValidationError(f"Child {index} needs a first name")

        try:
            age = int(spec.get('age'))
        except (TypeError, ValueError):
            raise ValidationError(f"Child {index} needs an age in whole years") from None

        lunch = LunchType.coerce(spec.get('lunch_type'))
        if lunch is None:
            raise ValidationError(f"Child {index} needs a valid lunch type")

        teacher_id = spec.get('teacher_id')
        if teacher_id is not None:
            try:
                teacher_id = int(teacher_id)
            except (TypeError, ValueError):
                raise ValidationError(f"Child {index} has an invalid teacher") from None
            if Teacher.query.filter_by(id=teacher_id).first() is None:
                raise ValidationError(f"Child {index} refers to a teacher who does not exist")

        return {
            'username': username,
            'password': spec.get('password'),
            'firstname': spec['firstname'].strip(),
            'age': age,
            'gender': (spec.get('gender') or '').strip() or 'Other',
            'race_ethnicity': spec.get('race_ethnicity'),
            'lunch_type': lunch,
            'teacher_id': teacher_id,
        }

    # ------------------------------------------------------------ teachers

    def register_teacher(self, *, username, email, password, firstname, lastname,
                         preschool_id=None):
        if not (username or '').strip():
            raise ValidationError("A username is required")
        if not password:
            raise ValidationError("A password is required")
        if not (firstname or '').strip() or not (lastname or '').strip():
            raise ValidationError("First and last name are required")

        self._require_free(username.strip(), email)

        try:
            teacher = Teacher(
                username=username.strip(),
                email=email,
                role=Role.TEACHER,
                firstname=firstname.strip(),
                lastname=lastname.strip(),
                preschool_id=int(preschool_id) if preschool_id else None,
            )
            teacher.set_password(password)
            self.db.session.add(teacher)
            self.db.session.commit()
            return teacher
        except Exception:
            self.db.session.rollback()
            raise

    # ---------------------------------------------------------------- auth

    @staticmethod
    def authenticate(username, password):
        """Verify credentials. Returns the User or None.

        Password hashes never leave this service -- that is the whole reason
        `web` posts credentials here rather than reading the users table.
        """
        if not username or not password:
            return None
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            return None
        return user
