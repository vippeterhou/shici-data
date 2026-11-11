import json
import sqlite3
from pathlib import Path

import pytest

from scripts.build_guangyun_lookup import SOURCE_PATH, build_lookup, load_source


def test_source_preserves_readings_aliases_and_provenance() -> None:
    readings, aliases, metadata = load_source(SOURCE_PATH)

    assert len(readings) == 24_320
    assert len(aliases) == 4_620
    assert ("東", "平", "東") in readings
    assert ("長", "平", "陽") in readings
    assert ("長", "上", "養") in readings
    assert ("長", "去", "漾") in readings
    assert ("清", "淸") in aliases
    assert "GNU GENERAL PUBLIC LICENSE" in metadata["license_text"]
    assert "UNICODE LICENSE V3" in metadata["unicode_license_text"]


def test_builds_query_database(tmp_path: Path) -> None:
    output = tmp_path / "guangyun_lookup.sqlite"

    counts = build_lookup(SOURCE_PATH, output)

    assert counts == {
        "character_readings": 24_320,
        "character_aliases": 4_620,
    }
    with sqlite3.connect(output) as database:
        assert database.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert set(
            database.execute(
                "SELECT character, tone, rhyme FROM character_readings "
                "WHERE character = '長'"
            )
        ) == {
            ("長", "平", "陽"),
            ("長", "上", "養"),
            ("長", "去", "漾"),
        }
        assert database.execute(
            "SELECT target_character FROM character_aliases "
            "WHERE input_character = '清'"
        ).fetchone() == ("淸",)
        metadata = dict(database.execute("SELECT key, value FROM metadata"))
    assert json.loads(metadata["dictionary"])["name"]


def test_build_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    build_lookup(SOURCE_PATH, first)
    build_lookup(SOURCE_PATH, second)

    assert first.read_bytes() == second.read_bytes()


def test_rejects_checksum_mismatch(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.jsonl"
    text = SOURCE_PATH.read_text(encoding="utf-8")
    invalid.write_text(
        text.replace(
            '{"character":"⿰隺犬","tone":"入","rhyme":"覺"}',
            '{"character":"⿰隺犬","tone":"入","rhyme":"屋"}',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_source(invalid)
