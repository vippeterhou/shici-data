import json
from pathlib import Path

import pytest

from scripts.build_release import Corpus, normalized_records, source_files


def test_source_files_are_sorted(tmp_path: Path) -> None:
    (tmp_path / "002.json").write_text("[]", encoding="utf-8")
    (tmp_path / "001.json").write_text("[]", encoding="utf-8")

    assert [path.name for path in source_files(tmp_path)] == [
        "001.json",
        "002.json",
    ]


def test_generates_stable_ids_for_missing_ids(tmp_path: Path) -> None:
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

    assert records[0]["id"] == "sample/001.json:0"


def test_normalizes_rhythmic_title(
    tmp_path: Path,
) -> None:
    record = {
        "rhythmic": "测试词牌",
        "author": "作者",
        "paragraphs": ["天地，玄黄、宇宙。"],
        "format": {
            "sentence_count": 3,
            "sentence_lengths": [2, 2, 2],
            "uniform_sentence_length": 2,
        },
        "tags": ["宋词三百首"],
    }
    source = tmp_path / "sc300.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("sc300", source)))

    assert records[0]["title"] == "测试词牌"


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
