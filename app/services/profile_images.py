"""Private on-disk storage for account profile images."""

from pathlib import Path, PurePosixPath
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def profile_upload_directory() -> Path:
    """The instance directory is outside Flask's public static tree."""
    configured = current_app.config.get("PROFILE_UPLOAD_DIR")
    directory = Path(configured or Path(current_app.instance_path) / "profile_uploads").resolve()
    if directory.is_relative_to(Path(current_app.static_folder).resolve()):
        raise RuntimeError("Profile uploads must be stored outside public static files")
    return directory


def profile_name(photo_path: str | None) -> str | None:
    """Accept a legacy database path, never an arbitrary filesystem path."""
    if not photo_path:
        return None
    path = PurePosixPath(photo_path)
    if len(path.parts) != 3 or path.parts[:2] != ("images", "profiles"):
        return None
    name = path.name
    if name in (".", "..") or secure_filename(name) != name:
        return None
    return name


def save_profile_image(upload, user_id: int) -> str:
    original = secure_filename(upload.filename or "")
    extension = Path(original).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".gif"}:
        raise ValueError("Unsupported profile image type")
    filename = f"user_{user_id}_{uuid4().hex}{extension}"
    directory = profile_upload_directory()
    directory.mkdir(parents=True, exist_ok=True)
    upload.save(directory / filename)
    return f"images/profiles/{filename}"
