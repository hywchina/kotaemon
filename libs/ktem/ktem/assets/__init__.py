from pathlib import Path
import shutil
import tempfile
import zipfile

from decouple import config

from .theme import Kotaemon as KotaemonTheme

PDFJS_VERSION_DIST: str = config("PDFJS_VERSION_DIST", "pdfjs-4.0.379-dist")
_PREBUILT_ROOT = Path(__file__).parent / "prebuilt"


def _ensure_pdfjs_dist(target: Path) -> Path:
    """Extract the bundled PDF.js archive without requiring runtime network access."""

    if target.is_dir():
        return target
    archive = _PREBUILT_ROOT / f"{PDFJS_VERSION_DIST}.zip"
    if not archive.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="pdfjs-", dir=target.parent))
    try:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_dir)
        try:
            temp_dir.replace(target)
        except FileExistsError:
            pass
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    return target


PDFJS_PREBUILT_DIR = _ensure_pdfjs_dist(
    Path(config("PDFJS_PREBUILT_DIR", _PREBUILT_ROOT / PDFJS_VERSION_DIST))
)

__all__ = ["KotaemonTheme", "PDFJS_VERSION_DIST", "PDFJS_PREBUILT_DIR"]
