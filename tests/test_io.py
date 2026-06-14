import pytest

from faso_speech.io import write_and_rename


def test_write_and_rename_replaces_file_after_success(tmp_path):
    output = tmp_path / "output.txt"
    output.write_text("old", encoding="utf-8")

    with write_and_rename(output, "w", encoding="utf-8") as output_file:
        output_file.write("new")

    assert output.read_text(encoding="utf-8") == "new"
    assert not output.with_name("output.txt.tmp").exists()


def test_write_and_rename_keeps_original_file_after_failure(tmp_path):
    output = tmp_path / "output.txt"
    output.write_text("old", encoding="utf-8")

    with pytest.raises(RuntimeError):
        with write_and_rename(output, "w", encoding="utf-8") as output_file:
            output_file.write("partial")
            raise RuntimeError("boom")

    assert output.read_text(encoding="utf-8") == "old"
    assert not output.with_name("output.txt.tmp").exists()
