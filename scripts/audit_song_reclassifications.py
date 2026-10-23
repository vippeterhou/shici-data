from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).parents[1]
DEFAULT_MANIFEST_PATH = (
    ROOT / "editorial" / "song-genre-reclassifications.json"
)
DEFAULT_QSC_DIRECTORY = ROOT / "raw" / "qsc"
DEFAULT_QSS_DIRECTORY = ROOT / "raw" / "qss"


def record_fingerprint(record: dict[str, object]) -> str:
    payload = json.dumps(
        [
            record["title"],
            record["author"],
            record["paragraphs"],
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_records(directory: Path) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = {}
    for path in sorted(directory.glob("*.json")):
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not all(
            isinstance(value, dict) for value in values
        ):
            raise ValueError(f"{path}: expected a list of records")
        records[path.name] = values
    return records


def audit_song_reclassifications(
    manifest_path: Path,
    qsc_directory: Path,
    qss_directory: Path,
) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid song genre reclassification manifest")
    changes = manifest.get("reclassifications")
    if not isinstance(changes, list):
        raise ValueError("reclassifications must be a list")

    qsc_records = load_records(qsc_directory)
    qss_records = load_records(qss_directory)
    records_by_corpus = {
        "qsc": qsc_records,
        "qss": qss_records,
    }
    fingerprints_by_corpus = {
        corpus: {
            record_fingerprint(record)
            for records in corpus_records.values()
            for record in records
        }
        for corpus, corpus_records in records_by_corpus.items()
    }

    seen_source_fingerprints: set[str] = set()
    removed_counts: Counter[str] = Counter()
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"reclassification {index} must be an object")
        source_corpus = change.get("from_corpus")
        retained_corpus = change.get("to_corpus")
        source_fingerprint = change.get("from_fingerprint")
        retained_fingerprint = change.get("retained_fingerprint")
        retained_file = change.get("retained_file")
        retained_index = change.get("retained_index")
        if (
            source_corpus not in records_by_corpus
            or retained_corpus not in records_by_corpus
            or not isinstance(source_fingerprint, str)
            or not isinstance(retained_fingerprint, str)
            or not isinstance(retained_file, str)
            or not isinstance(retained_index, int)
        ):
            raise ValueError(
                f"reclassification {index} has invalid audit fields"
            )
        if source_fingerprint in seen_source_fingerprints:
            raise ValueError(
                f"duplicate source fingerprint at reclassification {index}"
            )
        seen_source_fingerprints.add(source_fingerprint)
        removed_counts[source_corpus] += 1
        if source_fingerprint in fingerprints_by_corpus[source_corpus]:
            raise ValueError(
                f"reclassification {index} is still present in "
                f"{source_corpus.upper()}"
            )
        records = records_by_corpus[retained_corpus].get(retained_file)
        if records is None:
            raise ValueError(
                f"reclassification {index} has no retained "
                f"{retained_corpus.upper()} file"
            )
        if retained_index < 0 or retained_index >= len(records):
            raise ValueError(
                f"reclassification {index} retained "
                f"{retained_corpus.upper()} index is out of range"
            )
        if (
            record_fingerprint(records[retained_index])
            != retained_fingerprint
        ):
            raise ValueError(
                f"reclassification {index} retained index does not match "
                f"the {retained_corpus.upper()} record"
            )

    for corpus in records_by_corpus:
        expected_count = manifest.get(f"removed_from_{corpus}", 0)
        if expected_count != removed_counts[corpus]:
            raise ValueError(
                f"removed_from_{corpus} does not match the "
                "reclassification count"
            )
    return len(changes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit recorded QSC and QSS genre reclassifications."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
    )
    parser.add_argument(
        "--qsc-directory",
        type=Path,
        default=DEFAULT_QSC_DIRECTORY,
    )
    parser.add_argument(
        "--qss-directory",
        type=Path,
        default=DEFAULT_QSS_DIRECTORY,
    )
    arguments = parser.parse_args()
    count = audit_song_reclassifications(
        arguments.manifest,
        arguments.qsc_directory,
        arguments.qss_directory,
    )
    print(f"Song genre audit passed: {count} reclassifications verified.")


if __name__ == "__main__":
    main()
