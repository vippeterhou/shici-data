from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from scripts.build_release import QSC_COUNTED_CHARACTER, calculate_poem_format


ROOT = Path(__file__).parents[1]
DEFAULT_CORPUS_DIRECTORY = ROOT / "raw" / "qsc"
DEFAULT_LOCK_PATH = ROOT / "source-locks" / "qsc.json"
DEFAULT_CLEANUP_PATH = ROOT / "editorial" / "qsc-cleanup.json"
DEFAULT_GENRE_PATH = ROOT / "editorial" / "song-genre-reclassifications.json"
RAW_URL = "https://raw.githubusercontent.com/{repository}/{commit}/{path}"


def record_fingerprint(record: dict[str, object]) -> str:
    payload = json.dumps(
        [record["title"], record["author"], record["paragraphs"]],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def has_only_missing_text(text: str) -> bool:
    return "缺词文" in text and not re.sub(
        r"[（）()缺词文\s]",
        "",
        text,
    )


def source_indices(change: dict[str, object]) -> list[int]:
    index = change.get("source_index")
    indices = change.get("source_indices")
    start = change.get("start_index")
    end = change.get("end_index")
    if isinstance(index, int):
        return [index]
    if isinstance(indices, list) and all(
        isinstance(value, int) for value in indices
    ):
        return indices
    if isinstance(start, int) and isinstance(end, int) and start <= end:
        return list(range(start, end + 1))
    raise ValueError("editorial change has invalid source indices")


def git_source_fetcher(repository: Path, commit: str) -> Callable[[str], bytes]:
    def fetch(path: str) -> bytes:
        result = subprocess.run(
            ["git", "-C", str(repository), "show", f"{commit}:{path}"],
            check=True,
            capture_output=True,
        )
        return result.stdout

    return fetch


def remote_source_fetcher(
    repository: str,
    commit: str,
) -> Callable[[str], bytes]:
    def fetch(path: str) -> bytes:
        encoded_path = urllib.parse.quote(path)
        url = RAW_URL.format(
            repository=repository,
            commit=commit,
            path=encoded_path,
        )
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "shici-data-qsc-audit/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    return fetch


def load_source_records(
    lock: dict[str, object],
    fetch: Callable[[str], bytes],
) -> dict[str, list[dict[str, Any]]]:
    files = lock.get("files")
    if not isinstance(files, list):
        raise ValueError("QSC source lock has no files")
    records_by_file: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for file_lock in files:
        if not isinstance(file_lock, dict):
            raise ValueError("QSC source file lock must be an object")
        path = file_lock.get("path")
        output_file = file_lock.get("output_file")
        expected_hash = file_lock.get("sha256")
        expected_count = file_lock.get("record_count")
        if (
            not isinstance(path, str)
            or not isinstance(output_file, str)
            or not isinstance(expected_hash, str)
            or not isinstance(expected_count, int)
        ):
            raise ValueError("QSC source file lock has invalid fields")
        payload = fetch(path)
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(
                f"{path}: source hash mismatch; expected {expected_hash}, "
                f"got {actual_hash}"
            )
        values = json.loads(payload)
        if not isinstance(values, list) or len(values) != expected_count:
            raise ValueError(f"{path}: source record count mismatch")
        transformed: list[dict[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{index}: invalid source record")
            author = value.get("author")
            paragraphs = value.get("paragraphs")
            title = value.get("rhythmic")
            if (
                not isinstance(author, str)
                or not isinstance(title, str)
                or not isinstance(paragraphs, list)
                or not all(
                    isinstance(paragraph, str) for paragraph in paragraphs
                )
            ):
                raise ValueError(f"{path}:{index}: invalid source fields")
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
        raise ValueError("QSC total source record count mismatch")
    return records_by_file


def indexed_record(
    records_by_file: dict[str, list[dict[str, Any]]],
    source_file: object,
    index: int,
) -> dict[str, Any]:
    if not isinstance(source_file, str) or source_file not in records_by_file:
        raise ValueError(f"invalid QSC editorial source file: {source_file}")
    records = records_by_file[source_file]
    if index < 0 or index >= len(records):
        raise ValueError(
            f"{source_file}:{index}: editorial source index is invalid"
        )
    record = records[index]
    if record["_source_index"] != index:
        raise ValueError(f"{source_file}:{index}: source index drift")
    return record


def apply_author_suffix_normalizations(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("author_suffix_normalizations must be a list")
    source_counts = Counter(
        record["author"]
        for records in records_by_file.values()
        for record in records
    )
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("author suffix normalization must be an object")
        source_value = change.get("source_value")
        value = change.get("value")
        expected_count = change.get("record_count")
        if (
            not isinstance(source_value, str)
            or not isinstance(value, str)
            or not isinstance(expected_count, int)
        ):
            raise ValueError("invalid author suffix normalization")
        if source_counts[source_value] != expected_count:
            raise ValueError(
                f"author suffix count mismatch for {source_value}"
            )
        for records in records_by_file.values():
            for record in records:
                if record["author"] == source_value:
                    record["author"] = value


def apply_author_repairs(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("author_repairs must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("author repair must be an object")
        value = change.get("value")
        source_value = change.get("source_value")
        source_values = change.get("source_values")
        if not isinstance(value, str):
            raise ValueError("author repair has no value")
        allowed = (
            {source_value}
            if isinstance(source_value, str)
            else set(source_values)
            if isinstance(source_values, list)
            and all(isinstance(item, str) for item in source_values)
            else None
        )
        if allowed is None:
            raise ValueError("author repair has no source value")
        found: set[str] = set()
        for index in source_indices(change):
            record = indexed_record(
                records_by_file,
                change.get("source_file"),
                index,
            )
            if record["author"] not in allowed:
                raise ValueError(
                    f"{change.get('source_file')}:{index}: "
                    "author repair source mismatch"
                )
            found.add(record["author"])
            record["author"] = value
        if found != allowed:
            raise ValueError("author repair did not match every source value")


def apply_title_repairs(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("title_repairs must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("title repair must be an object")
        source_value = change.get("source_value")
        value = change.get("value")
        if not isinstance(source_value, str) or not isinstance(value, str):
            raise ValueError("invalid title repair")
        for index in source_indices(change):
            record = indexed_record(
                records_by_file,
                change.get("source_file"),
                index,
            )
            if record["title"] != source_value:
                raise ValueError("title repair source mismatch")
            record["title"] = value


def apply_paragraph_repairs(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("paragraph_repairs must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("paragraph repair must be an object")
        source_value = change.get("source_value")
        value = change.get("value")
        paragraph_index = change.get("paragraph_index")
        if (
            not isinstance(source_value, str)
            or not isinstance(value, str)
            or not isinstance(paragraph_index, int)
        ):
            raise ValueError("invalid paragraph repair")
        indices = source_indices(change)
        if len(indices) != 1:
            raise ValueError("paragraph repair must target one record")
        record = indexed_record(
            records_by_file,
            change.get("source_file"),
            indices[0],
        )
        paragraphs = record["paragraphs"]
        if (
            paragraph_index < 0
            or paragraph_index >= len(paragraphs)
            or paragraphs[paragraph_index] != source_value
        ):
            raise ValueError(
                f"{change.get('source_file')}:{indices[0]}:"
                f"{paragraph_index}: paragraph repair source mismatch"
            )
        paragraphs[paragraph_index] = value


def apply_paragraph_removals(
    records_by_file: dict[str, list[dict[str, Any]]],
    changes: object,
) -> None:
    if not isinstance(changes, list):
        raise ValueError("paragraph_removals must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("paragraph removal must be an object")
        paragraph_index = change.get("paragraph_index")
        source_value = change.get("source_value")
        if not isinstance(paragraph_index, int) or not isinstance(
            source_value, str
        ):
            raise ValueError("invalid paragraph removal")
        indices = source_indices(change)
        if len(indices) != 1:
            raise ValueError("paragraph removal must target one record")
        record = indexed_record(
            records_by_file,
            change.get("source_file"),
            indices[0],
        )
        paragraphs = record["paragraphs"]
        if (
            paragraph_index < 0
            or paragraph_index >= len(paragraphs)
            or paragraphs[paragraph_index] != source_value
        ):
            raise ValueError("paragraph removal source mismatch")
        del paragraphs[paragraph_index]


def genre_removal_locations(manifest: dict[str, object]) -> set[tuple[str, int]]:
    changes = manifest.get("reclassifications")
    if not isinstance(changes, list):
        raise ValueError("invalid song genre manifest")
    locations: set[tuple[str, int]] = set()
    for change in changes:
        if not isinstance(change, dict) or change.get("from_corpus") != "qsc":
            continue
        source_file = change.get("from_file")
        source_index = change.get("from_index")
        if not isinstance(source_file, str) or not isinstance(
            source_index, int
        ):
            raise ValueError("invalid QSC genre removal")
        locations.add((source_file, source_index))
    return locations


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
        indices = source_indices(change)
        if len(indices) != 1:
            raise ValueError("record removal must target one record")
        source_file = change.get("source_file")
        if not isinstance(source_file, str):
            raise ValueError("record removal has invalid source file")
        record = indexed_record(records_by_file, source_file, indices[0])
        kind = change.get("kind")
        if kind == "exact_duplicate":
            duplicate_of_index = change.get("duplicate_of_index")
            if not isinstance(duplicate_of_index, int):
                raise ValueError("duplicate removal has no source record")
            duplicate = indexed_record(
                records_by_file,
                source_file,
                duplicate_of_index,
            )
            if record_fingerprint(record) != record_fingerprint(duplicate):
                raise ValueError("record removal is not an exact duplicate")
        elif kind == "unrecoverable_missing_text":
            text = "".join(record["paragraphs"])
            if not has_only_missing_text(text):
                raise ValueError(
                    "record removal contains recoverable text"
                )
        else:
            raise ValueError("record removal has invalid kind")
        locations.add((source_file, indices[0]))
    return locations


def join_suite_record(
    records: list[dict[str, Any]],
    replacements: object,
) -> dict[str, object]:
    if not records:
        raise ValueError("cannot consolidate an empty QSC suite")
    paragraphs: list[str] = []
    for record in records:
        source_paragraphs = record["paragraphs"]
        if len(source_paragraphs) < 3:
            raise ValueError("QSC suite stanza is too short")
        paragraphs.extend(source_paragraphs[:2])
        tail: list[str] = []
        for index, paragraph in enumerate(source_paragraphs[2:]):
            if index < len(source_paragraphs[2:]) - 1:
                if not paragraph.endswith("。"):
                    raise ValueError("QSC suite paragraph has no separator")
                paragraph = f"{paragraph[:-1]}，"
            tail.append(paragraph)
        paragraphs.append("".join(tail))
    if not isinstance(replacements, dict) or not all(
        isinstance(source, str) and isinstance(value, str)
        for source, value in replacements.items()
    ):
        raise ValueError("QSC consolidation replacements are invalid")
    for source, value in replacements.items():
        paragraphs = [
            paragraph.replace(source, value) for paragraph in paragraphs
        ]
    return {
        "title": records[0]["title"],
        "author": records[0]["author"],
        "paragraphs": paragraphs,
    }


def consolidate_records(
    records_by_file: dict[str, list[dict[str, Any]]],
    consolidations: object,
    removals: set[tuple[str, int]],
) -> dict[str, list[dict[str, object]]]:
    if not isinstance(consolidations, list):
        raise ValueError("QSC consolidations must be a list")
    groups_by_file: dict[
        str, dict[int, tuple[int, dict[str, object]]]
    ] = {}
    grouped_indices: set[tuple[str, int]] = set()
    for change in consolidations:
        if not isinstance(change, dict):
            raise ValueError("QSC consolidation must be an object")
        output_file = change.get("output_file")
        start = change.get("start_index")
        end = change.get("end_index")
        if (
            not isinstance(output_file, str)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start > end
        ):
            raise ValueError("invalid QSC consolidation")
        source_records = [
            indexed_record(records_by_file, output_file, index)
            for index in range(start, end + 1)
        ]
        value = join_suite_record(
            source_records,
            change.get("text_replacements", {}),
        )
        groups_by_file.setdefault(output_file, {})[start] = (end, value)
        grouped_indices.update(
            (output_file, index) for index in range(start, end + 1)
        )

    output: dict[str, list[dict[str, object]]] = {}
    for output_file, records in records_by_file.items():
        transformed: list[dict[str, object]] = []
        groups = groups_by_file.get(output_file, {})
        skipped_until = -1
        for record in records:
            index = record["_source_index"]
            if index <= skipped_until:
                continue
            group = groups.get(index)
            if group is not None:
                skipped_until, value = group
                transformed.append(value)
                continue
            location = (output_file, index)
            if location in grouped_indices or location in removals:
                continue
            transformed.append(
                {
                    "title": record["title"],
                    "author": record["author"],
                    "paragraphs": record["paragraphs"],
                }
            )
        for record in transformed:
            record["format"] = calculate_poem_format(
                record["paragraphs"],
                "qsc",
            )
        output[output_file] = transformed
    return output


def expected_qsc_records(
    lock: dict[str, object],
    cleanup: dict[str, object],
    genre: dict[str, object],
    fetch: Callable[[str], bytes],
) -> dict[str, list[dict[str, object]]]:
    records_by_file = load_source_records(lock, fetch)
    genre_removals = genre_removal_locations(genre)
    for source_file, index in genre_removals:
        record = indexed_record(records_by_file, source_file, index)
        expected = next(
            change["from_fingerprint"]
            for change in genre["reclassifications"]
            if change.get("from_corpus") == "qsc"
            and change.get("from_file") == source_file
            and change.get("from_index") == index
        )
        if record_fingerprint(record) != expected:
            raise ValueError("QSC genre removal fingerprint mismatch")
    apply_author_suffix_normalizations(
        records_by_file,
        cleanup.get("author_suffix_normalizations", []),
    )
    apply_author_repairs(
        records_by_file,
        cleanup.get("author_repairs", []),
    )
    apply_title_repairs(
        records_by_file,
        cleanup.get("title_repairs", []),
    )
    apply_paragraph_repairs(
        records_by_file,
        cleanup.get("paragraph_repairs", []),
    )
    apply_paragraph_removals(
        records_by_file,
        cleanup.get("paragraph_removals", []),
    )
    removals = genre_removals | cleanup_removal_locations(
        records_by_file,
        cleanup.get("record_removals", []),
    )
    return consolidate_records(
        records_by_file,
        lock.get("consolidations", []),
        removals,
    )


def validate_qsc_quality(
    records_by_file: dict[str, list[dict[str, object]]],
    expected_unresolved: object | None = None,
) -> None:
    fingerprints: Counter[str] = Counter()
    unresolved = Counter()
    for output_file, records in records_by_file.items():
        for index, record in enumerate(records):
            location = f"{output_file}:{index}"
            combined = (
                f"{record['title']}{record['author']}"
                f"{''.join(record['paragraphs'])}"
            )
            if "�" in combined:
                raise ValueError(f"{location}: replacement character remains")
            if re.search(r"\d$", str(record["author"])):
                raise ValueError(f"{location}: numeric author suffix remains")
            text = "".join(record["paragraphs"])
            lacuna_count = text.count("□")
            if lacuna_count:
                unresolved["lacuna_records"] += 1
                unresolved["lacuna_occurrences"] += lacuna_count
                known_count = len(QSC_COUNTED_CHARACTER.findall(text))
                if lacuna_count / (known_count + lacuna_count) >= 0.25:
                    unresolved["lacuna_at_least_25_percent"] += 1
            if has_only_missing_text(text):
                raise ValueError(f"{location}: record has no recoverable text")
            if "缺词文" in text:
                unresolved["partial_missing_text_records"] += 1
            if "（上缺）" in text or "（下缺）" in text:
                unresolved["explicit_truncation_records"] += 1
            if "□" in str(record["author"]):
                unresolved["author_placeholder_records"] += 1
            if "□" in str(record["title"]):
                unresolved["title_placeholder_records"] += 1
            fingerprints[record_fingerprint(record)] += 1
    if any(count > 1 for count in fingerprints.values()):
        raise ValueError("QSC contains exact duplicate records")
    if expected_unresolved is not None:
        if not isinstance(expected_unresolved, dict) or not all(
            isinstance(key, str) and isinstance(value, int)
            for key, value in expected_unresolved.items()
        ):
            raise ValueError("invalid expected_unresolved counts")
        actual = {
            key: unresolved[key] for key in expected_unresolved
        }
        if actual != expected_unresolved:
            raise ValueError(
                "QSC unresolved-defect counts changed: "
                f"expected {expected_unresolved}, got {actual}"
            )


def load_local_records(
    directory: Path,
) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = {}
    for path in sorted(directory.glob("*.json")):
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not all(
            isinstance(value, dict) for value in values
        ):
            raise ValueError(f"{path}: invalid QSC records")
        records[path.name] = values
    return records


def audit_qsc(
    corpus_directory: Path,
    lock_path: Path,
    cleanup_path: Path,
    genre_path: Path,
    source_repository: Path | None,
) -> int:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    genre = json.loads(genre_path.read_text(encoding="utf-8"))
    if not all(
        isinstance(value, dict) for value in (lock, cleanup, genre)
    ):
        raise ValueError("invalid QSC audit metadata")
    repository = lock.get("repository")
    commit = lock.get("commit")
    if not isinstance(repository, str) or not isinstance(commit, str):
        raise ValueError("QSC source lock has invalid repository or commit")
    fetch = (
        git_source_fetcher(source_repository, commit)
        if source_repository is not None
        else remote_source_fetcher(repository, commit)
    )
    expected = expected_qsc_records(lock, cleanup, genre, fetch)
    local = load_local_records(corpus_directory)
    if local.keys() != expected.keys():
        raise ValueError("QSC source file set mismatch")
    for output_file in expected:
        if local[output_file] != expected[output_file]:
            for index, (actual, wanted) in enumerate(
                zip(local[output_file], expected[output_file])
            ):
                if actual != wanted:
                    raise ValueError(
                        f"{output_file}:{index}: QSC source mismatch"
                    )
            raise ValueError(f"{output_file}: QSC record count mismatch")
    validate_qsc_quality(local, cleanup.get("expected_unresolved"))
    count = sum(len(records) for records in local.values())
    if count != lock.get("release_record_count"):
        raise ValueError("QSC release record count mismatch")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit QSC against its pinned upstream revision."
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
        help="Use a local chinese-poetry Git repository instead of GitHub.",
    )
    arguments = parser.parse_args()
    count = audit_qsc(
        arguments.corpus_directory,
        arguments.lock,
        arguments.cleanup,
        arguments.genre,
        arguments.source_repository,
    )
    print(f"QSC audit passed: {count} records verified.")


if __name__ == "__main__":
    main()
