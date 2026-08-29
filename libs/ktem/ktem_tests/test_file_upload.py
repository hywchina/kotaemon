import stat
import zipfile

import pytest

from ktem.utils.file_upload import safe_extract_zip
from ktem.utils.notifications import UserFacingError


def test_safe_extract_zip_extracts_regular_files(tmp_path):
    archive = tmp_path / "documents.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("department/report.txt", "safe content")

    extracted = safe_extract_zip(
        archive,
        tmp_path / "output",
        max_files=10,
        max_uncompressed_bytes=1024,
    )

    assert [path.relative_to(tmp_path / "output").as_posix() for path in extracted] == [
        "department/report.txt"
    ]
    assert extracted[0].read_text() == "safe content"


@pytest.mark.parametrize("member_name", ["../outside.txt", "..\\outside.txt"])
def test_safe_extract_zip_rejects_parent_paths(tmp_path, member_name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(member_name, "unsafe")

    with pytest.raises(UserFacingError, match="不安全"):
        safe_extract_zip(
            archive,
            tmp_path / "output",
            max_files=10,
            max_uncompressed_bytes=1024,
        )

    assert not (tmp_path / "outside.txt").exists()


def test_safe_extract_zip_enforces_file_and_size_limits(tmp_path):
    archive = tmp_path / "large.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("one.txt", "12345")
        output.writestr("two.txt", "67890")

    with pytest.raises(UserFacingError, match="文件数"):
        safe_extract_zip(
            archive,
            tmp_path / "count-output",
            max_files=1,
            max_uncompressed_bytes=100,
        )

    with pytest.raises(UserFacingError, match="总大小"):
        safe_extract_zip(
            archive,
            tmp_path / "size-output",
            max_files=10,
            max_uncompressed_bytes=5,
        )


def test_safe_extract_zip_rejects_symbolic_links(tmp_path):
    archive = tmp_path / "link.zip"
    link = zipfile.ZipInfo("report-link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(link, "target.txt")

    with pytest.raises(UserFacingError, match="符号链接"):
        safe_extract_zip(
            archive,
            tmp_path / "output",
            max_files=10,
            max_uncompressed_bytes=1024,
        )
