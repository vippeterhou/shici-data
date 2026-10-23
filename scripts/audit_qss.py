from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from scripts.build_release import (
    Corpus,
    QSC_COUNTED_CHARACTER,
    calculate_poem_format,
    validate_raw_record,
)
from scripts.source_audit import git_source_fetcher, remote_source_fetcher


ROOT = Path(__file__).parents[1]
DEFAULT_CORPUS_DIRECTORY = ROOT / "raw" / "qss"
DEFAULT_LOCK_PATH = ROOT / "source-locks" / "qss.json"
DEFAULT_CLEANUP_PATH = ROOT / "editorial" / "qss-cleanup.json"
DEFAULT_GENRE_PATH = ROOT / "editorial" / "song-genre-reclassifications.json"


def record_fingerprint(record: dict[str, object]) -> str:
    payload = json.dumps(
        [record["title"], record["author"], record["paragraphs"]],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_record(
    records_by_file: dict[str, list[dict[str, Any]]],
    source_file: object,
    source_index: object,
) -> dict[str, Any]:
    if (
        not isinstance(source_file, str)
        or source_file not in records_by_file
        or not isinstance(source_index, int)
    ):
        raise ValueError("invalid QSS source location")
    records = records_by_file[source_file]
    if source_index < 0 or source_index >= len(records):
        raise ValueError("QSS source index is out of range")
    record = records[source_index]
    if record["_source_index"] != source_index:
        raise ValueError("QSS source index drift")
    return record


def load_source_records(
    lock: dict[str, object],
    fetch: Callable[[str], bytes],
) -> dict[str, list[dict[str, Any]]]:
    files = lock.get("files")
    if not isinstance(files, list):
        raise ValueError("QSS source lock has no files")
    validated_files: list[dict[str, object]] = []
    for file_lock in files:
        if not isinstance(file_lock, dict):
            raise ValueError("QSS source file lock must be an object")
        if not (
            isinstance(file_lock.get("path"), str)
            and isinstance(file_lock.get("output_file"), str)
            and isinstance(file_lock.get("sha256"), str)
            and isinstance(file_lock.get("record_count"), int)
        ):
            raise ValueError("QSS source file lock has invalid fields")
        validated_files.append(file_lock)
    with ThreadPoolExecutor(max_workers=8) as executor:
        payloads = list(
            executor.map(
                lambda item: fetch(item["path"]),
                validated_files,
            )
        )
    records_by_file: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for file_lock, payload in zip(validated_files, payloads):
        path = file_lock.get("path")
        output_file = file_lock.get("output_file")
        expected_hash = file_lock.get("sha256")
        expected_count = file_lock.get("record_count")
        assert isinstance(path, str)
        assert isinstance(output_file, str)
        assert isinstance(expected_hash, str)
        assert isinstance(expected_count, int)
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ValueError(f"{path}: QSS source hash mismatch")
        values = json.loads(payload)
        if not isinstance(values, list) or len(values) != expected_count:
            raise ValueError(f"{path}: QSS source record count mismatch")
        transformed: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{index}: invalid QSS record")
            title = value.get("title")
            author = value.get("author")
            paragraphs = value.get("paragraphs")
            if (
                not isinstance(title, str)
                or not isinstance(author, str)
                or not isinstance(paragraphs, list)
                or not all(isinstance(item, str) for item in paragraphs)
            ):
                raise ValueError(f"{path}:{index}: invalid QSS fields")
            transformed.append(
                {
                    "title": title,
                    "author": author,
                    "paragraphs": list(paragraphs),
                    "_source_index": index,
                }
            )
        records_by_file[output_file] = transformed
        total += len(transformed)
    if total != lock.get("record_count"):
        raise ValueError("QSS total source record count mismatch")
    return records_by_file


def genre_removal_locations(
    records_by_file: dict[str, list[dict[str, Any]]],
    genre: dict[str, object],
) -> set[tuple[str, int]]:
    changes = genre.get("reclassifications")
    if not isinstance(changes, list):
        raise ValueError("invalid Song genre manifest")
    locations: set[tuple[str, int]] = set()
    for change in changes:
        if not isinstance(change, dict) or change.get("from_corpus") != "qss":
            continue
        source_file = change.get("from_file")
        source_index = change.get("from_index")
        expected_fingerprint = change.get("from_fingerprint")
        record = source_record(records_by_file, source_file, source_index)
        if record_fingerprint(record) != expected_fingerprint:
            raise ValueError("QSS genre removal fingerprint mismatch")
        locations.add((source_file, source_index))
    if len(locations) != genre.get("removed_from_qss"):
        raise ValueError("QSS genre removal count mismatch")
    return locations


def apply_paragraph_removals(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("paragraph_removals must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("paragraph removal must be an object")
        record = source_record(
            records_by_file,
            change.get("source_file"),
            change.get("source_index"),
        )
        paragraph_index = change.get("paragraph_index")
        source_value = change.get("source_value")
        if (
            not isinstance(paragraph_index, int)
            or paragraph_index < 0
            or paragraph_index >= len(record["paragraphs"])
            or record["paragraphs"][paragraph_index] != source_value
        ):
            raise ValueError("QSS paragraph removal mismatch")
        del record["paragraphs"][paragraph_index]


def apply_metadata_repairs(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
    field: str,
) -> None:
    if not isinstance(changes, list):
        raise ValueError(f"{field}_repairs must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError(f"{field} repair must be an object")
        record = source_record(
            records_by_file,
            change.get("source_file"),
            change.get("source_index"),
        )
        source_value = change.get("source_value")
        value = change.get("value")
        if (
            not isinstance(source_value, str)
            or not isinstance(value, str)
            or record[field] != source_value
        ):
            raise ValueError(f"QSS {field} repair mismatch")
        record[field] = value


def cleanup_removal_locations(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> set[tuple[str, int]]:
    if not isinstance(changes, list):
        raise ValueError("record_removals must be a list")
    locations: set[tuple[str, int]] = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("record removal must be an object")
        source_file = change.get("source_file")
        source_index = change.get("source_index")
        record = source_record(records_by_file, source_file, source_index)
        kind = change.get("kind")
        if kind == "exact_duplicate":
            duplicate = source_record(
                records_by_file,
                source_file=change.get("duplicate_of_file"),
                source_index=change.get("duplicate_of_index"),
            )
            if record_fingerprint(record) != record_fingerprint(duplicate):
                raise ValueError("QSS record removal is not a duplicate")
        elif kind == "empty_text":
            if record["paragraphs"]:
                raise ValueError("QSS empty-text removal has text")
        elif kind == "all_placeholders":
            text = "".join(record["paragraphs"])
            if "□" not in text or re.sub(r"[□，。！？；：、\s]", "", text):
                raise ValueError("QSS placeholder removal has surviving text")
        else:
            raise ValueError("QSS record removal has invalid kind")
        location = (source_file, source_index)
        if location in locations:
            raise ValueError("duplicate QSS cleanup removal")
        locations.add(location)
    return locations


def expected_qss_records(
    lock: dict[str, object],
    cleanup: dict[str, object],
    genre: dict[str, object],
    fetch: Callable[[str], bytes],
) -> dict[str, list[dict[str, object]]]:
    source = load_source_records(lock, fetch)
    apply_metadata_repairs(source, cleanup.get("author_repairs"), "author")
    apply_metadata_repairs(source, cleanup.get("title_repairs"), "title")
    apply_paragraph_removals(source, cleanup.get("paragraph_removals"))
    removals = cleanup_removal_locations(
        source,
        cleanup.get("record_removals"),
    )
    removals.update(genre_removal_locations(source, genre))
    expected: dict[str, list[dict[str, object]]] = {}
    for source_file, records in source.items():
        transformed = []
        for record in records:
            location = (source_file, record["_source_index"])
            if location in removals:
                continue
            paragraphs = list(record["paragraphs"])
            transformed.append(
                {
                    "title": record["title"],
                    "author": record["author"],
                    "paragraphs": paragraphs,
                    "format": calculate_poem_format(paragraphs, "qss"),
                }
            )
        expected[source_file] = transformed
    return expected


def unresolved_counts(
    records_by_file: dict[str, list[dict[str, object]]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for records in records_by_file.values():
        for record in records:
            title = record["title"]
            author = record["author"]
            paragraphs = record["paragraphs"]
            if not (
                isinstance(title, str)
                and isinstance(author, str)
                and isinstance(paragraphs, list)
            ):
                raise ValueError("invalid QSS record fields")
            text = "".join(paragraphs)
            occurrences = text.count("□")
            if occurrences:
                counts["lacuna_records"] += 1
                counts["lacuna_occurrences"] += occurrences
                characters = len(QSC_COUNTED_CHARACTER.findall(text))
                if characters and occurrences / (
                    characters + occurrences
                ) >= 0.25:
                    counts["lacuna_at_least_25_percent"] += 1
            counts["author_placeholder_records"] += "□" in author
            counts["title_placeholder_records"] += "□" in title
    return dict(counts)


def validate_qss_quality(
    records_by_file: dict[str, list[dict[str, object]]],
    expected_unresolved: object,
) -> None:
    fingerprints: set[str] = set()
    corpus = Corpus("qss", Path("."))
    for source_file, records in records_by_file.items():
        for index, record in enumerate(records):
            validate_raw_record(
                record,
                corpus,
                Path(source_file),
                index,
            )
            if any(not paragraph for paragraph in record["paragraphs"]):
                raise ValueError("QSS record has an empty paragraph")
            if "�" in json.dumps(record, ensure_ascii=False):
                raise ValueError("QSS record has a replacement character")
            fingerprint = record_fingerprint(record)
            if fingerprint in fingerprints:
                raise ValueError("QSS corpus has an exact duplicate")
            fingerprints.add(fingerprint)
    actual = unresolved_counts(records_by_file)
    if actual != expected_unresolved:
        raise ValueError(
            "QSS unresolved-defect counts changed: "
            f"expected {expected_unresolved}, got {actual}"
        )


def load_local_records(
    corpus_directory: Path,
) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = {}
    for path in sorted(corpus_directory.glob("*.json")):
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not all(
            isinstance(value, dict) for value in values
        ):
            raise ValueError(f"{path}: invalid QSS records")
        records[path.name] = values
    return records


def audit_qss(
    corpus_directory: Path,
    lock_path: Path,
    cleanup_path: Path,
    genre_path: Path,
    source_repository: Path | None,
) -> int:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    genre = json.loads(genre_path.read_text(encoding="utf-8"))
    if not all(isinstance(item, dict) for item in (lock, cleanup, genre)):
        raise ValueError("invalid QSS audit metadata")
    repository = lock.get("repository")
    commit = lock.get("commit")
    if not isinstance(repository, str) or not isinstance(commit, str):
        raise ValueError("invalid QSS source lock")
    fetch = (
        git_source_fetcher(source_repository, commit)
        if source_repository is not None
        else remote_source_fetcher(repository, commit)
    )
    expected = expected_qss_records(lock, cleanup, genre, fetch)
    local = load_local_records(corpus_directory)
    if local != expected:
        for source_file in expected:
            if source_file not in local:
                raise ValueError(f"{source_file}: missing local QSS shard")
            for index, (actual, wanted) in enumerate(
                zip(local[source_file], expected[source_file])
            ):
                if actual != wanted:
                    raise ValueError(
                        f"{source_file}:{index}: QSS source mismatch"
                    )
            if len(local[source_file]) != len(expected[source_file]):
                raise ValueError(f"{source_file}: QSS record count mismatch")
        raise ValueError("QSS local file set mismatch")
    validate_qss_quality(local, cleanup.get("expected_unresolved"))
    count = sum(len(records) for records in local.values())
    if count != lock.get("release_record_count"):
        raise ValueError("QSS release record count mismatch")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit QSS against its pinned upstream revision."
    )
    parser.add_argument(
        "--corpus-directory",
        type=Path,
        default=DEFAULT_CORPUS_DIRECTORY,
    )
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument(
        "--cleanup",
        type=Path,
        default=DEFAULT_CLEANUP_PATH,
    )
    parser.add_argument("--genre", type=Path, default=DEFAULT_GENRE_PATH)
    parser.add_argument(
        "--source-repository",
        type=Path,
        help="Use a local chinese-poetry repository instead of GitHub.",
    )
    arguments = parser.parse_args()
    count = audit_qss(
        arguments.corpus_directory,
        arguments.lock,
        arguments.cleanup,
        arguments.genre,
        arguments.source_repository,
    )
    print(f"QSS audit passed: {count} records verified.")


if __name__ == "__main__":
    main()
