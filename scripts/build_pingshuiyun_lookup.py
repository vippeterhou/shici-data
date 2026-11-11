from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).parents[1]
SOURCE_PATH = ROOT / "raw" / "rhyme" / "pingshuiyun_lookup.json"
OUTPUT_PATH = ROOT / "build" / "pingshuiyun_lookup.sqlite"
EXPECTED_SECTION_COUNTS = {
    "upper_level": 15,
    "lower_level": 15,
    "rising": 29,
    "departing": 30,
    "entering": 17,
}
SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA page_size = 4096;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE rhyme_groups (
    id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL,
    section TEXT NOT NULL,
    tone TEXT NOT NULL CHECK (tone IN ('平', '上', '去', '入')),
    register TEXT CHECK (register IN ('上', '下') OR register IS NULL),
    ordinal INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE (section_id, ordinal)
) WITHOUT ROWID;

CREATE TABLE character_rhymes (
    character TEXT NOT NULL,
    rhyme_id TEXT NOT NULL REFERENCES rhyme_groups(id),
    is_supplement INTEGER NOT NULL CHECK (is_supplement IN (0, 1)),
    supplement_kind TEXT NOT NULL,
    source_order INTEGER NOT NULL,
    PRIMARY KEY (character, rhyme_id, is_supplement, supplement_kind)
) WITHOUT ROWID;

CREATE INDEX character_rhymes_character_idx
ON character_rhymes(character);

CREATE TABLE character_aliases (
    input_character TEXT NOT NULL,
    target_character TEXT NOT NULL,
    PRIMARY KEY (input_character, target_character)
) WITHOUT ROWID;

CREATE INDEX character_aliases_target_idx
ON character_aliases(target_character);

CREATE VIEW character_lookup AS
SELECT
    character_rhymes.character,
    character_rhymes.character AS canonical_character,
    rhyme_groups.tone,
    rhyme_groups.register,
    rhyme_groups.ordinal,
    rhyme_groups.name AS rhyme,
    rhyme_groups.section,
    character_rhymes.is_supplement,
    character_rhymes.supplement_kind,
    'canonical' AS match_type
FROM character_rhymes
JOIN rhyme_groups ON rhyme_groups.id = character_rhymes.rhyme_id
UNION ALL
SELECT
    character_aliases.input_character AS character,
    character_rhymes.character AS canonical_character,
    rhyme_groups.tone,
    rhyme_groups.register,
    rhyme_groups.ordinal,
    rhyme_groups.name AS rhyme,
    rhyme_groups.section,
    character_rhymes.is_supplement,
    character_rhymes.supplement_kind,
    'alias' AS match_type
FROM character_aliases
JOIN character_rhymes
    ON character_rhymes.character = character_aliases.target_character
JOIN rhyme_groups ON rhyme_groups.id = character_rhymes.rhyme_id;
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as source_file:
        source = json.load(source_file)
    if source.get("schema_version") != 2:
        raise ValueError(f"{path}: unsupported schema version")
    sections = source.get("sections")
    if not isinstance(sections, list) or len(sections) != 5:
        raise ValueError(f"{path}: expected five tone sections")
    actual_counts = {
        section.get("id"): len(section.get("rhymes", []))
        for section in sections
        if isinstance(section, dict)
    }
    if actual_counts != EXPECTED_SECTION_COUNTS:
        raise ValueError(f"{path}: expected the canonical 106 rhyme groups")
    aliases = source.get("aliases")
    if not isinstance(aliases, dict) or not aliases:
        raise ValueError(f"{path}: expected simplified query aliases")
    for input_character, targets in aliases.items():
        if (
            not isinstance(input_character, str)
            or len(input_character) != 1
            or not isinstance(targets, list)
            or not targets
            or any(not isinstance(target, str) or len(target) != 1 for target in targets)
        ):
            raise ValueError(f"{path}: invalid alias mapping")
    return source


def add_characters(
    rows: dict[tuple[str, str, int, str], tuple[object, ...]],
    characters: str,
    rhyme_id: str,
    is_supplement: int,
    supplement_kind: str,
) -> None:
    if not characters or any(character.isspace() for character in characters):
        raise ValueError(f"{rhyme_id}: invalid character list")
    for order, character in enumerate(characters):
        key = (character, rhyme_id, is_supplement, supplement_kind)
        rows.setdefault(
            key,
            (character, rhyme_id, is_supplement, supplement_kind, order),
        )


def build_lookup(source_path: Path, output_path: Path) -> dict[str, int]:
    source = load_source(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.unlink(missing_ok=True)

    groups: list[tuple[object, ...]] = []
    character_rows: dict[
        tuple[str, str, int, str],
        tuple[object, ...],
    ] = {}
    for section in source["sections"]:
        section_id = section["id"]
        rhymes = section["rhymes"]
        for expected_ordinal, rhyme in enumerate(rhymes, start=1):
            ordinal = rhyme["ordinal"]
            if ordinal != expected_ordinal:
                raise ValueError(
                    f"{section_id}: expected rhyme {expected_ordinal}, got {ordinal}"
                )
            rhyme_id = f"{section_id}:{ordinal:02d}"
            groups.append(
                (
                    rhyme_id,
                    section_id,
                    section["name"],
                    section["tone"],
                    section["register"],
                    ordinal,
                    rhyme["name"],
                )
            )
            add_characters(
                character_rows,
                rhyme["characters"],
                rhyme_id,
                0,
                "",
            )
            for supplement in rhyme["supplements"]:
                supplement_kind = supplement["kind"]
                add_characters(
                    character_rows,
                    supplement["characters"],
                    rhyme_id,
                    1,
                    supplement_kind,
                )

    canonical_characters = {key[0] for key in character_rows}
    aliases = [
        (input_character, target_character)
        for input_character, targets in source["aliases"].items()
        for target_character in targets
    ]
    if any(target not in canonical_characters for _, target in aliases):
        raise ValueError("Alias target is missing from the canonical rhyme table")

    dictionary = {
        "name": source["name"],
        "scope": "106韵",
        "license": "MIT",
        "maintainer": "vippeterhou/shici-data",
    }
    metadata = {
        "dictionary": json.dumps(dictionary, ensure_ascii=False, sort_keys=True),
        "description": source["description"],
        "query_aliases": str(len(aliases)),
        "license_text": (
            "Project-maintained transcription released under the repository "
            "MIT License. The historical rhyme classification is public domain."
        ),
        "schema_version": "2",
        "source_data_sha256": sha256(source_path),
    }

    try:
        with sqlite3.connect(temporary_path) as database:
            database.executescript(SCHEMA)
            database.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                sorted(metadata.items()),
            )
            database.executemany(
                "INSERT INTO rhyme_groups VALUES (?, ?, ?, ?, ?, ?, ?)",
                groups,
            )
            database.executemany(
                "INSERT INTO character_rhymes VALUES (?, ?, ?, ?, ?)",
                sorted(character_rows.values()),
            )
            database.executemany(
                "INSERT INTO character_aliases VALUES (?, ?)",
                aliases,
            )
            database.execute("PRAGMA user_version = 2")
            database.commit()
            database.execute("VACUUM")
            if database.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("Generated Pingshuiyun lookup failed integrity check")
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "rhyme_groups": len(groups),
        "character_rhymes": len(character_rows),
        "character_aliases": len(aliases),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    counts = build_lookup(args.source, args.output)
    print(
        f"Built {args.output} with {counts['rhyme_groups']} rhyme groups "
        f"and {counts['character_rhymes']} canonical character mappings "
        f"plus {counts['character_aliases']} query aliases"
    )


if __name__ == "__main__":
    main()
