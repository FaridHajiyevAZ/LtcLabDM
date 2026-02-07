import os
import hashlib
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _file_hash(file_storage):
    """Compute SHA-256 hash of an uploaded file without consuming it."""
    hasher = hashlib.sha256()
    file_storage.seek(0)
    while True:
        chunk = file_storage.read(8192)
        if not chunk:
            break
        hasher.update(chunk)
    file_storage.seek(0)
    return hasher.hexdigest()


def save_upload(file_storage, subfolder="general"):
    """Save an uploaded file and return (relative_path, original_filename, file_hash, file_size).

    Raises ValueError on validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided.")

    original_filename = secure_filename(file_storage.filename)
    if not _allowed_file(original_filename):
        raise ValueError(
            f"File type not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    max_size = current_app.config.get("MAX_FILE_SIZE", 5 * 1024 * 1024)
    if size > max_size:
        raise ValueError(f"File too large. Maximum size: {max_size // (1024*1024)}MB")

    content_hash = _file_hash(file_storage)

    # Generate unique filename to prevent overwrites
    ext = original_filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    upload_root = current_app.config.get("UPLOAD_FOLDER", "uploads")
    dest_dir = os.path.join(upload_root, subfolder)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, unique_name)
    file_storage.save(dest_path)

    # Return path relative to upload root
    relative_path = os.path.join(subfolder, unique_name)
    return relative_path, original_filename, content_hash, size


def delete_upload(relative_path):
    """Delete a previously uploaded file."""
    upload_root = current_app.config.get("UPLOAD_FOLDER", "uploads")
    full_path = os.path.join(upload_root, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
