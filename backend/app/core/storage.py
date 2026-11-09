import logging
from pathlib import Path

from app.core.config import settings

log = logging.getLogger(__name__)


def _path(rel: str) -> Path:
    root = Path(settings.media_dir).resolve()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise ValueError("Bad media path")
    return path


def save_media(rel: str, data: bytes) -> None:
    path = _path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)                    # a half-written file is never visible


def delete_media(rel: str) -> None:
    try:
        _path(rel).unlink(missing_ok=True)
    except (OSError, ValueError):
        log.exception("Could not delete media file %s", rel)