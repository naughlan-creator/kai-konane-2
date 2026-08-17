"""Shared handling for content images.

Activities and stories both let an author either upload a new picture or pick
one that is already in the library, so that logic lives in one place.
"""
import os

from werkzeug.utils import secure_filename

from app.config import basedir

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'images')
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif'}


def library_images():
    """Every image already available to pick from, alphabetically."""
    if not os.path.isdir(UPLOAD_FOLDER):
        return []
    return sorted(
        name for name in os.listdir(UPLOAD_FOLDER)
        if os.path.splitext(name)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def is_library_image(filename):
    if not filename:
        return False
    safe = secure_filename(filename)
    return bool(safe) and os.path.isfile(os.path.join(UPLOAD_FOLDER, safe))


def save_upload(image):
    """Store an uploaded image and return its filename, or None.

    Returns None for a missing file, an empty filename or a disallowed
    extension, so callers can treat "nothing supplied" and "not usable" the same.
    """
    if not image or not getattr(image, 'filename', ''):
        return None

    filename = secure_filename(image.filename)
    if not filename:
        return None
    if os.path.splitext(filename)[1].lower() not in ALLOWED_IMAGE_EXTENSIONS:
        return None

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    image.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def resolve_image(upload=None, existing_choice=None, current=None):
    """Pick the image to use, in priority order.

    A fresh upload wins; then a filename chosen from the library; then whatever
    the record already had. Returning `current` is what stops an edit that does
    not touch the picture from wiping it.
    """
    saved = save_upload(upload)
    if saved:
        return saved
    if existing_choice and is_library_image(existing_choice):
        return secure_filename(existing_choice)
    return current
