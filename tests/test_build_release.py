import json
from pathlib import Path

import pytest

from scripts.build_release import (
    Corpus,
    calculate_poem_format,
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


def test_placeholder_counts_as_sentence_character(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地□黄。"],
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

    assert list(normalized_records(Corpus("qts", source)))[0]["format"] == {
        "sentence_count": 1,
        "sentence_lengths": [4],
        "uniform_sentence_length": 4,
    }


def test_rejects_format_that_excludes_placeholder(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地□黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [3],
            "uniform_sentence_length": 3,
        },
    }
    source = tmp_path / "001.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="format mismatch"):
        list(normalized_records(Corpus("qts", source)))


def test_sc300_uses_ideographic_comma_as_sentence_boundary() -> None:
    assert calculate_poem_format(
        ["更多少、无情风雨。"],
        "sc300",
    ) == {
        "sentence_count": 2,
        "sentence_lengths": [3, 4],
        "uniform_sentence_length": None,
    }


def test_rejects_incorrect_sc300_format(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["更多少、无情风雨。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [7],
            "uniform_sentence_length": 7,
        },
    }
    source = tmp_path / "sc300.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="format mismatch"):
        list(normalized_records(Corpus("sc300", source)))


def test_qsc_uses_ideographic_comma_and_counts_lacunae() -> None:
    assert calculate_poem_format(
        ["更多少、无情□风雨。"],
        "qsc",
    ) == {
        "sentence_count": 2,
        "sentence_lengths": [3, 5],
        "uniform_sentence_length": None,
    }


def test_qss_counts_lacunae_and_compatibility_ideographs() -> None:
    assert calculate_poem_format(
        ["山路﨑□嶇。"],
        "qss",
    ) == {
        "sentence_count": 1,
        "sentence_lengths": [5],
        "uniform_sentence_length": 5,
    }


def test_ascii_exclamation_separates_sentences() -> None:
    assert calculate_poem_format(["噫!天地玄黄。"]) == {
        "sentence_count": 2,
        "sentence_lengths": [1, 4],
        "uniform_sentence_length": None,
    }


def test_rejects_incorrect_qsc_format(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["更多少、无情□风雨。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [8],
            "uniform_sentence_length": 8,
        },
    }
    source = tmp_path / "001.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="format mismatch"):
        list(normalized_records(Corpus("qsc", source)))


@pytest.mark.parametrize("separator", ["：", ":", ";"])
def test_colon_and_ascii_semicolon_separate_sentences(
    separator: str,
) -> None:
    assert calculate_poem_format([f"乱曰{separator}天地玄黄。"]) == {
        "sentence_count": 2,
        "sentence_lengths": [2, 4],
        "uniform_sentence_length": None,
    }
