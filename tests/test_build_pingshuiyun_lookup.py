import json
import sqlite3
from pathlib import Path

import pytest

from scripts.build_pingshuiyun_lookup import SOURCE_PATH, build_lookup, load_source


def test_source_has_canonical_106_rhyme_groups() -> None:
    source = load_source(SOURCE_PATH)

    assert sum(len(section["rhymes"]) for section in source["sections"]) == 106
    assert [len(section["rhymes"]) for section in source["sections"]] == [
        15,
        15,
        29,
        30,
        17,
    ]
    assert all(
        "characters_simplified" not in rhyme
        for section in source["sections"]
        for rhyme in section["rhymes"]
    )
    assert source["aliases"]["东"] == ["東"]


def test_builds_both_scripts_and_preserves_multiple_rhymes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "pingshuiyun_lookup.sqlite"

    counts = build_lookup(SOURCE_PATH, output)

    assert counts["rhyme_groups"] == 106
    with sqlite3.connect(output) as database:
        assert database.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert database.execute(
            "SELECT rhyme, canonical_character, match_type FROM character_lookup "
            "WHERE character = '东' AND tone = '平'"
        ).fetchone() == ("東", "東", "alias")
        assert database.execute(
            "SELECT rhyme, canonical_character, match_type FROM character_lookup "
            "WHERE character = '東' AND tone = '平'"
        ).fetchone() == ("東", "東", "canonical")
        assert database.execute(
            "SELECT COUNT(DISTINCT tone || ':' || rhyme) "
            "FROM character_lookup WHERE character = '重'"
        ).fetchone()[0] > 1
        assert database.execute(
            "SELECT COUNT(*) FROM character_aliases"
        ).fetchone()[0] == counts["character_aliases"]
        metadata = dict(database.execute("SELECT key, value FROM metadata"))
    assert json.loads(metadata["dictionary"])["scope"] == "106韵"
    assert metadata["source_data_sha256"]


def test_build_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    build_lookup(SOURCE_PATH, first)
    build_lookup(SOURCE_PATH, second)

    assert first.read_bytes() == second.read_bytes()


def test_rejects_incomplete_source(tmp_path: Path) -> None:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    source["sections"][0]["rhymes"].pop()
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical 106"):
        load_source(invalid)
