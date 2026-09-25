import json
from pathlib import Path

import pytest

from scripts.build_release import (
    Corpus,
    content_id,
    normalized_records,
    source_files,
)


def test_source_files_are_sorted(tmp_path: Path) -> None:
    (tmp_path / "002.json").write_text("[]", encoding="utf-8")
    (tmp_path / "001.json").write_text("[]", encoding="utf-8")

    assert [path.name for path in source_files(tmp_path)] == [
        "001.json",
        "002.json",
    ]


def test_generates_content_id(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    (tmp_path / "001.json").write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("sample", tmp_path)))

    assert records[0]["id"] == content_id("sample", record)


def test_content_id_is_independent_of_file_location(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    serialized = json.dumps([record], ensure_ascii=False)
    first.write_text(serialized, encoding="utf-8")
    second.write_text(serialized, encoding="utf-8")

    first_id = list(normalized_records(Corpus("sample", first)))[0]["id"]
    second_id = list(normalized_records(Corpus("sample", second)))[0]["id"]

    assert first_id == second_id


def test_rejects_missing_format(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
    }
    source = tmp_path / "001.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing format"):
        list(normalized_records(Corpus("sample", source)))


def test_suffixes_duplicate_content_ids(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    source = tmp_path / "001.json"
    source.write_text(
        json.dumps([record, record], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("sample", source)))
    base_id = content_id("sample", record)

    assert [value["id"] for value in records] == [base_id, f"{base_id}:2"]


def test_rejects_extra_or_misordered_raw_fields(tmp_path: Path) -> None:
    record = {
        "author": "作者",
        "title": "测试",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    source = tmp_path / "001.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fields must be"):
        list(normalized_records(Corpus("sample", source)))
