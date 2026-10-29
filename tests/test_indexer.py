"""Tests for src.agent.indexer."""

import logging
from pathlib import Path

import pytest

from src.agent.extractors.base import ExtractedDocument, Segment
from src.agent.indexer import IndexResult, index_documents, iter_document_files

logger = logging.getLogger("test")


def test_empty_dir_returns_zero(tmp_path: Path) -> None:
    result = index_documents(tmp_path, logger)
    assert result.files_found == 0
    assert result.files_processed == 0
    assert result.segments_total == 0
    assert result.files_with_zero_segments == 0
    assert result.files_skipped == 0


def test_nonexistent_root_returns_zero_and_logs_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    nonexistent = tmp_path / "does_not_exist"
    with caplog.at_level(logging.ERROR):
        result = index_documents(nonexistent, logger)
    assert result.files_found == 0
    assert "does not exist" in caplog.text


def test_single_md_file(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        "# First\n\nHello world.\n\n# Second\n\nAnother section.",
        encoding="utf-8",
    )
    result = index_documents(tmp_path, logger)
    assert result.files_found == 1
    assert result.files_processed == 1
    assert result.segments_total == 2
    assert result.files_with_zero_segments == 0


def test_multiple_files_with_nested_dirs(tmp_path: Path) -> None:
    (tmp_path / "a" / "foo.md").parent.mkdir(parents=True)
    (tmp_path / "a" / "foo.md").write_text("# A\n\nText A.", encoding="utf-8")
    (tmp_path / "b" / "bar.md").parent.mkdir(parents=True)
    (tmp_path / "b" / "bar.md").write_text("# B\n\nText B.", encoding="utf-8")
    (tmp_path / "c" / "baz.txt").parent.mkdir(parents=True)
    (tmp_path / "c" / "baz.txt").write_text("Plain text.", encoding="utf-8")
    result = index_documents(tmp_path, logger)
    assert result.files_found == 3
    assert result.files_processed == 3


def test_ignores_unknown_extensions(tmp_path: Path) -> None:
    (tmp_path / "file.md").write_text("# Title\n\nContent.", encoding="utf-8")
    (tmp_path / "file.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "file.json").write_text('{"a": 1}', encoding="utf-8")
    result = index_documents(tmp_path, logger)
    assert result.files_found == 1


def test_ignores_subdirectory_markers(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.md").write_text("# Nested", encoding="utf-8")
    only_dirs = tmp_path / "only_dirs"
    only_dirs.mkdir()
    (only_dirs / "a").mkdir()
    (only_dirs / "b").mkdir()
    result = index_documents(only_dirs, logger)
    assert result.files_found == 0


def test_broken_encoding_counts_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.agent.indexer.extract_text", lambda p: None)
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00\x00")
    result = index_documents(tmp_path, logger)
    assert result.files_skipped == 1
    assert result.files_processed == 0


def test_files_with_zero_segments_counted(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("   \n\n   ", encoding="utf-8")
    result = index_documents(tmp_path, logger)
    assert result.files_with_zero_segments == 1


def test_on_progress_called_per_file(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\n\nText.", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\nText.", encoding="utf-8")
    calls: list[tuple[int, int, Path, ExtractedDocument | None]] = []
    result = index_documents(
        tmp_path,
        logger,
        on_progress=lambda i, total, path, doc: calls.append((i, total, path, doc)),
    )
    assert len(calls) == result.files_found
    for i, (idx, total, path, doc) in enumerate(calls, start=1):
        assert idx == i
        assert total == result.files_found
        assert isinstance(path, Path)
        assert isinstance(doc, ExtractedDocument)


def test_on_progress_none_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text("# X\n\nContent.", encoding="utf-8")
    result = index_documents(tmp_path, logger, on_progress=None)
    assert result.files_processed == 1


def test_summary_contains_key_numbers(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("# Title\n\nBody.", encoding="utf-8")
    result = index_documents(tmp_path, logger)
    summary = result.summary()
    assert "Файлов найдено:" in summary
    assert str(result.files_found) in summary
    assert "Сегментов" in summary
