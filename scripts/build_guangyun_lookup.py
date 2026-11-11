from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).parents[1]
SOURCE_PATH = ROOT / "raw" / "rhyme" / "guangyun_lookup.jsonl"
OUTPUT_PATH = ROOT / "build" / "guangyun_lookup.sqlite"
VALID_TONES = frozenset({"平", "上", "去", "入"})
READING_FIELDS = frozenset({"character", "tone", "rhyme"})
ALIAS_FIELDS = frozenset({"input_character", "target_character"})
METADATA_FIELDS = frozenset({"metadata_key", "value"})
REQUIRED_METADATA_KEYS = frozenset(
    {
        "dictionary",
        "character_variants",
        "character_search",
        "source_database_sha256",
        "license_text",
        "unicode_license_text",
        "canonical_data",
    }
)


def json_line(record: dict[str, Any]) -> str:
    return (
        json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )


def require_text(value: Any, field: str, path: Path, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}:{line_number}: {field} must be a non-empty string")
    return value


def canonical_data_sha256(
    readings: list[tuple[str, str, str]],
    aliases: list[tuple[str, str]],
) -> str:
    digest = hashlib.sha256()
    for character, tone, rhyme in readings:
        digest.update(
            json_line(
                {
                    "character": character,
                    "tone": tone,
                    "rhyme": rhyme,
                }
            ).encode()
        )
    for input_character, target_character in aliases:
        digest.update(
            json_line(
                {
                    "input_character": input_character,
                    "target_character": target_character,
                }
            ).encode()
        )
    return digest.hexdigest()


def load_source(
    source_path: Path,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]], dict[str, Any]]:
    readings: list[tuple[str, str, str]] = []
    aliases: list[tuple[str, str]] = []
    metadata: dict[str, Any] = {}
    seen_readings: set[tuple[str, str, str]] = set()
    seen_aliases: set[tuple[str, str]] = set()
    section = 0

    with source_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(
                    f"{source_path}:{line_number}: blank lines are not allowed"
                )
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{source_path}:{line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"{source_path}:{line_number}: record must be an object"
                )

            fields = frozenset(record)
            if fields == READING_FIELDS:
                if section:
                    raise ValueError(
                        f"{source_path}:{line_number}: readings must come first"
                    )
                reading = (
                    require_text(
                        record["character"],
                        "character",
                        source_path,
                        line_number,
                    ),
                    require_text(record["tone"], "tone", source_path, line_number),
                    require_text(record["rhyme"], "rhyme", source_path, line_number),
                )
                if reading[1] not in VALID_TONES:
                    raise ValueError(
                        f"{source_path}:{line_number}: invalid tone {reading[1]!r}"
                    )
                if reading in seen_readings:
                    raise ValueError(
                        f"{source_path}:{line_number}: duplicate reading"
                    )
                seen_readings.add(reading)
                readings.append(reading)
            elif fields == ALIAS_FIELDS:
                if section > 1:
                    raise ValueError(
                        f"{source_path}:{line_number}: aliases must precede metadata"
                    )
                section = 1
                alias = (
                    require_text(
                        record["input_character"],
                        "input_character",
                        source_path,
                        line_number,
                    ),
                    require_text(
                        record["target_character"],
                        "target_character",
                        source_path,
                        line_number,
                    ),
                )
                if alias in seen_aliases:
                    raise ValueError(f"{source_path}:{line_number}: duplicate alias")
                seen_aliases.add(alias)
                aliases.append(alias)
            elif fields == METADATA_FIELDS:
                section = 2
                key = require_text(
                    record["metadata_key"],
                    "metadata_key",
                    source_path,
                    line_number,
                )
                if key in metadata:
                    raise ValueError(
                        f"{source_path}:{line_number}: duplicate metadata key {key!r}"
                    )
                metadata[key] = record["value"]
            else:
                raise ValueError(
                    f"{source_path}:{line_number}: unsupported fields "
                    f"{', '.join(sorted(fields))}"
                )

    if readings != sorted(readings):
        raise ValueError(f"{source_path}: readings must use stable lexical ordering")
    if aliases != sorted(aliases):
        raise ValueError(f"{source_path}: aliases must use stable lexical ordering")
    if list(metadata) != sorted(metadata):
        raise ValueError(f"{source_path}: metadata must use stable key ordering")

    reading_characters = {character for character, _, _ in readings}
    if any(target not in reading_characters for _, target in aliases):
        raise ValueError(f"{source_path}: alias target has no canonical reading")
    missing_metadata = REQUIRED_METADATA_KEYS - metadata.keys()
    if missing_metadata:
        raise ValueError(
            f"{source_path}: missing metadata keys: "
            f"{', '.join(sorted(missing_metadata))}"
        )
    canonical_data = metadata["canonical_data"]
    if not isinstance(canonical_data, dict):
        raise ValueError(f"{source_path}: invalid canonical_data metadata")
    expected_checksum = canonical_data.get("data_sha256")
    actual_checksum = canonical_data_sha256(readings, aliases)
    if expected_checksum != actual_checksum:
        raise ValueError(f"{source_path}: canonical data checksum mismatch")

    return readings, aliases, metadata


def build_lookup(source_path: Path, output_path: Path) -> dict[str, int]:
    readings, aliases, metadata = load_source(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=output_path.parent,
        suffix=".sqlite",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with sqlite3.connect(temporary_path) as database:
            database.execute("PRAGMA journal_mode = DELETE")
            database.execute("PRAGMA synchronous = FULL")
            database.executescript(
                """
                CREATE TABLE character_readings (
                    character TEXT NOT NULL CHECK (character != ''),
                    tone TEXT NOT NULL CHECK (tone IN ('平', '上', '去', '入')),
                    rhyme TEXT NOT NULL CHECK (rhyme != ''),
                    PRIMARY KEY (character, tone, rhyme)
                ) WITHOUT ROWID;
                CREATE TABLE character_aliases (
                    input_character TEXT NOT NULL CHECK (input_character != ''),
                    target_character TEXT NOT NULL CHECK (target_character != ''),
                    PRIMARY KEY (input_character, target_character)
                ) WITHOUT ROWID;
                CREATE INDEX character_aliases_target_idx
                    ON character_aliases (target_character);
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                ) WITHOUT ROWID;
                """
            )
            database.executemany(
                "INSERT INTO character_readings VALUES (?, ?, ?)",
                readings,
            )
            database.executemany(
                "INSERT INTO character_aliases VALUES (?, ?)",
                aliases,
            )
            database.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                [
                    (
                        key,
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    )
                    for key, value in sorted(metadata.items())
                ],
            )
            database.commit()
            if database.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Generated Guangyun lookup failed integrity check")
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "character_readings": len(readings),
        "character_aliases": len(aliases),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    counts = build_lookup(args.source, args.output)
    print(
        f"Built {args.output} with {counts['character_readings']} readings "
        f"and {counts['character_aliases']} query aliases"
    )


if __name__ == "__main__":
    main()
