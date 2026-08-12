import pytest

from defeat_watermarker.io_utils import BoundedIOError, atomic_write_text, read_bounded_bytes


def test_bounded_read_rejects_file_over_limit(tmp_path) -> None:
    path = tmp_path / "input.bin"
    path.write_bytes(b"12345")
    with pytest.raises(BoundedIOError, match="exceeds 4 bytes"):
        read_bounded_bytes(path, max_bytes=4)


def test_atomic_write_replaces_complete_text(tmp_path) -> None:
    path = tmp_path / "nested" / "evidence.json"
    atomic_write_text(path, "first\n")
    atomic_write_text(path, "second\n")
    assert path.read_text(encoding="utf-8") == "second\n"
    assert not list(path.parent.glob("*.tmp"))


def test_atomic_write_enforces_output_bound(tmp_path) -> None:
    with pytest.raises(BoundedIOError, match="output exceeds"):
        atomic_write_text(tmp_path / "out.txt", "12345", max_bytes=4)
