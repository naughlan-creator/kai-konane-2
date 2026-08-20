"""web's own Role enum.

Deliberately duplicated from the api rather than imported. Sharing a code module
across a service boundary would put `web` back inside the api's package and undo
the split; duplicating a four-member protocol constant is the correct trade, the
same way two services agreeing on an HTTP status code is not duplication.

The api sends a role as `{"name": "PARENT", "value": "PARENT"}`. It must become
a real enum member here, because every route guard compares
`current_user.role == Role.PARENT`. A dict never equals an enum and raises
nothing -- the guard would simply reject everyone, silently.
"""
from enum import Enum


class Role(Enum):
    ADMIN = "ADMIN"
    CHILD = "CHILD"
    PARENT = "PARENT"
    TEACHER = "TEACHER"

    @classmethod
    def coerce(cls, value, default=None):
        """Accept a member, a name, or the api's `{name, value}` payload."""
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            value = value.get('name')
        if value is None:
            return default
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            return default