import json
import sqlite3
from pathlib import Path

import pytest
import scripts.build_release as release

from scripts.build_guangyun_lookup import (
    SOURCE_PATH as GUANGYUN_SOURCE_PATH,
    build_lookup as build_guangyun_lookup,
)
from scripts.build_pingshuiyun_lookup import (
    SOURCE_PATH as PINGSHUIYUN_SOURCE_PATH,
    build_lookup as build_pingshuiyun_lookup,
)
from scripts.build_release import (
    CORPORA,
    Corpus,
    calculate_poem_format,
    content_id,
    normalized_records,
    source_files,
    text_id,
    work_id,
)


def test_release_copies_guangyun_with_checksum_and_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "guangyun.sqlite"
    db = sqlite3.connect(source)
    db.executescript(
        "CREATE TABLE character_readings (character TEXT, tone TEXT, rhyme TEXT);"
        "CREATE TABLE character_aliases "
        "(input_character TEXT, target_character TEXT);"
        "CREATE TABLE metadata (key TEXT, value TEXT);"
        "INSERT INTO character_readings VALUES ('淸', '平', '淸');"
        "INSERT INTO character_readings VALUES ('⿰隺犬', '入', '覺');"
        "INSERT INTO character_aliases VALUES ('清', '淸');"
    )
    metadata = {
        "dictionary": json.dumps({
            "name": "Test dictionary",
            "source_url": "https://example.org/dictionary",
            "license": "GPL-2.0",
        }),
        "license_text": "Test license notice",
    }
    db.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    db.commit()
    db.close()
    pingshuiyun = tmp_path / "pingshuiyun.sqlite"
    build_pingshuiyun_lookup(PINGSHUIYUN_SOURCE_PATH, pingshuiyun)
    monkeypatch.setattr(release, "CORPORA", ())
    monkeypatch.setattr(release, "DIST_DIRECTORY", tmp_path / "dist")
    monkeypatch.setattr(release, "MANIFEST_PATH", tmp_path / "manifest.json")

    manifest = release.build_release("local", source, pingshuiyun)

    output = tmp_path / "dist" / "guangyun_lookup.sqlite"
    assert output.read_bytes() == source.read_bytes()
    assert manifest["dictionaries"]["guangyun"] == {
        "asset": output.name,
        "bytes": output.stat().st_size,
        "sha256": release.sha256(source),
    }
    assert json.loads((tmp_path / "dist" / "manifest.json").read_text()) == manifest


def test_invalid_guangyun_preserves_existing_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    existing = output / "manifest.json"
    existing.write_text("existing release")
    monkeypatch.setattr(release, "DIST_DIRECTORY", output)

    with pytest.raises(ValueError, match="not found"):
        release.build_release(
            "local",
            tmp_path / "missing.sqlite",
            tmp_path / "unused.sqlite",
        )

    assert existing.read_text() == "existing release"


def test_release_includes_independent_pingshuiyun_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "pingshuiyun.sqlite"
    build_pingshuiyun_lookup(PINGSHUIYUN_SOURCE_PATH, source)
    guangyun = tmp_path / "guangyun.sqlite"
    build_guangyun_lookup(GUANGYUN_SOURCE_PATH, guangyun)
    monkeypatch.setattr(release, "CORPORA", ())
    monkeypatch.setattr(release, "DIST_DIRECTORY", tmp_path / "dist")
    monkeypatch.setattr(release, "MANIFEST_PATH", tmp_path / "manifest.json")

    manifest = release.build_release("local", guangyun, source)

    output = tmp_path / "dist" / "pingshuiyun_lookup.sqlite"
    assert output.read_bytes() == source.read_bytes()
    assert manifest["dictionaries"]["pingshuiyun"] == {
        "asset": output.name,
        "bytes": output.stat().st_size,
        "sha256": release.sha256(source),
    }


def test_hwlcs_combines_dynasties_without_qin() -> None:
    corpora = {corpus.name: corpus for corpus in CORPORA}

    assert "qinhan" not in corpora
    assert "wjnbc" not in corpora
    assert "hanweiliuchaoshi" not in corpora
    corpus = corpora["hwlcs"]
    assert corpus.source.parent.name == "hwlcs"
    assert [path.name for path in source_files(corpus.source)] == [
        "hwlcs.json",
    ]
    records = list(normalized_records(corpus))
    assert len(records) == 1554
    assert all(record["id"].startswith("hwlcs:") for record in records)
    assert len({record["id"] for record in records}) == len(records)


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


def test_qts_groups_matching_author_and_text_under_work_id(
    tmp_path: Path,
) -> None:
    first = {
        "title": "乐府题名",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    second = {**first, "title": "作者专卷题名"}
    source = tmp_path / "017.json"
    source.write_text(
        json.dumps([first, second], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("qts", source)))

    assert records[0]["id"] != records[1]["id"]
    assert records[0]["work_id"] == records[1]["work_id"]
    assert records[0]["work_id"] == work_id("qts", first)
    assert records[0]["text_id"] == records[1]["text_id"]
    assert records[0]["text_id"] == text_id("qts", first)
    assert records[0]["volume"] == 17
    assert records[1]["volume"] == 17


def test_qts_work_id_distinguishes_authors(tmp_path: Path) -> None:
    first = {
        "title": "测试",
        "author": "作者甲",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    second = {**first, "author": "作者乙"}
    source = tmp_path / "017.json"
    source.write_text(
        json.dumps([first, second], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("qts", source)))

    assert records[0]["work_id"] != records[1]["work_id"]
    assert records[0]["text_id"] == records[1]["text_id"]


def test_qss_groups_matching_author_and_text_under_work_id(
    tmp_path: Path,
) -> None:
    first = {
        "title": "题名之一",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    second = {**first, "title": "题名之二"}
    source = tmp_path / "qss.json"
    source.write_text(
        json.dumps([first, second], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("qss", source)))

    assert records[0]["id"] != records[1]["id"]
    assert records[0]["work_id"] == records[1]["work_id"]
    assert records[0]["work_id"] == work_id("qss", first)
    assert records[0]["text_id"] == records[1]["text_id"]
    assert records[0]["text_id"] == text_id("qss", first)


def test_qss_text_id_links_different_attributions(tmp_path: Path) -> None:
    first = {
        "title": "测试",
        "author": "作者甲",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [4],
            "uniform_sentence_length": 4,
        },
    }
    second = {**first, "author": "作者乙"}
    source = tmp_path / "qss.json"
    source.write_text(
        json.dumps([first, second], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("qss", source)))

    assert records[0]["work_id"] != records[1]["work_id"]
    assert records[0]["text_id"] == records[1]["text_id"]


def test_qss_cross_references_keep_independent_identities(
    tmp_path: Path,
) -> None:
    first = {
        "title": "七言再咏",
        "author": "石元规",
        "paragraphs": ["詩見張繼先三。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [6],
            "uniform_sentence_length": 6,
        },
    }
    second = {**first, "title": "同游栖真联句"}
    source = tmp_path / "qss.json"
    source.write_text(
        json.dumps([first, second], ensure_ascii=False),
        encoding="utf-8",
    )

    records = list(normalized_records(Corpus("qss", source)))

    assert records[0]["work_id"] != records[1]["work_id"]
    assert records[0]["text_id"] != records[1]["text_id"]


def test_non_identity_corpus_records_do_not_include_work_id(
    tmp_path: Path,
) -> None:
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
    source = tmp_path / "sample.json"
    source.write_text(
        json.dumps([record], ensure_ascii=False),
        encoding="utf-8",
    )

    normalized = list(normalized_records(Corpus("sample", source)))[0]

    assert "work_id" not in normalized


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


@pytest.mark.parametrize(
    "corpus_name",
    [corpus.name for corpus in CORPORA],
)
def test_rejects_incorrect_calculated_format(
    tmp_path: Path,
    corpus_name: str,
) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄。"],
        "format": {
            "sentence_count": 1,
            "sentence_lengths": [3],
            "uniform_sentence_length": 3,
        },
    }
    if corpus_name == "shijing":
        record["chapter"] = "国风"
        record["section"] = "周南"
    source = tmp_path / f"{corpus_name}.json"
    source.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="format mismatch"):
        list(normalized_records(Corpus(corpus_name, source)))


def test_rejects_ts300_spacing_between_sentences(tmp_path: Path) -> None:
    record = {
        "title": "测试",
        "author": "作者",
        "paragraphs": ["天地玄黄　宇宙洪荒"],
        "format": {
            "sentence_count": 2,
            "sentence_lengths": [4, 4],
            "uniform_sentence_length": 4,
        },
    }
    source = tmp_path / "ts300.json"
    source.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="must use punctuation"):
        list(normalized_records(Corpus("ts300", source)))


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
