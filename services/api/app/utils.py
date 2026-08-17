"""Small helpers shared across models and services."""
from datetime import datetime, timezone


def utcnow():
    """Current UTC time as a naive datetime.

    The DateTime columns are timezone-naive and store UTC by convention, so this
    deliberately drops the tzinfo after converting. Mixing aware and naive
    values in one column raises on comparison, and SQLite cannot store an offset
    at all -- so the convention is enforced here, in one place.

    datetime.utcnow() did exactly this but is deprecated from Python 3.12.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcdate():
    """Today's date in UTC, not the server's local timezone."""
    return datetime.now(timezone.utc).date()


def as_iso(value):
    """Serialise a naive-UTC datetime to unambiguous ISO 8601.

    A naive .isoformat() emits no offset, so a client cannot tell which zone it
    is in. Attaching UTC at the boundary keeps storage simple and the wire
    format precise -- which is what docs/architecture.md promises.
    """
    if value is None:
        return None
    if hasattr(value, "tzinfo") and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
