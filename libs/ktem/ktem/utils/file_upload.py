"""Safety helpers for files supplied through the upload interface."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path, PurePosixPath

from ktem.utils.notifications import UserFacingError


def _validated_member_path(output_dir: Path, member: zipfile.ZipInfo) -> Path:
    """Return a safe local path for one archive member."""

    archive_path = PurePosixPath(member.filename.replace("\\", "/"))
    if archive_path.is_absolute() or ".." in archive_path.parts:
        raise UserFacingError("压缩包包含不安全的文件路径，已拒绝解压。")

    mode = member.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise UserFacingError("压缩包包含符号链接，已拒绝解压。")

    target = (output_dir / Path(*archive_path.parts)).resolve()
    if not target.is_relative_to(output_dir):
        raise UserFacingError("压缩包包含越界文件路径，已拒绝解压。")
    return target


def safe_extract_zip(
    archive_path: str | Path,
    output_dir: str | Path,
    *,
    max_files: int,
    max_uncompressed_bytes: int,
) -> list[Path]:
    """Extract a ZIP archive after enforcing path and resource limits."""

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    try:
        archive = zipfile.ZipFile(archive_path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise UserFacingError("压缩包无法读取或文件已损坏。") from exc

    extracted: list[Path] = []
    with archive:
        file_members = [member for member in archive.infolist() if not member.is_dir()]
        if len(file_members) > max_files:
            raise UserFacingError(f"压缩包内文件数超过 {max_files} 个限制。")

        declared_size = sum(member.file_size for member in file_members)
        if declared_size > max_uncompressed_bytes:
            size_mb = max_uncompressed_bytes // (1024 * 1024)
            raise UserFacingError(f"压缩包解压后总大小超过 {size_mb} MB 限制。")

        extracted_bytes = 0
        for member in archive.infolist():
            target = _validated_member_path(destination, member)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    extracted_bytes += len(chunk)
                    if extracted_bytes > max_uncompressed_bytes:
                        raise UserFacingError("压缩包实际解压大小超过系统限制。")
                    output.write(chunk)
            extracted.append(target)

    return extracted
