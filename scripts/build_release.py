from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).parents[1]
RAW_DIRECTORY = ROOT / "raw"
DIST_DIRECTORY = ROOT / "dist"
MANIFEST_PATH = ROOT / "manifest.json"
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Corpus:
    name: str
    source: Path


CORPORA = (
    Corpus("shijing", RAW_DIRECTORY / "shijing" / "shijing.json"),
    Corpus("qinhan", RAW_DIRECTORY / "qinhan"),
    Corpus("weijinnanbeichao", RAW_DIRECTORY / "weijinnanbeichao"),
    Corpus("ts300", RAW_DIRECTORY / "ts300" / "ts300.json"),
    Corpus("qts", RAW_DIRECTORY / "qts"),
    Corpus("sc300", RAW_DIRECTORY / "sc300" / "sc300.json"),
    Corpus("quansongci", RAW_DIRECTORY / "quansongci"),
    Corpus("quansongshi", RAW_DIRECTORY / "quansongshi"),
)

SENTENCE_SEPARATOR = re.compile(r"[，。！？；：、,.!?;:]+")


def source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        files = sorted(source.glob("*.json"))
        if files:
            return files
    raise ValueError(f"No JSON source files found at {source}")


def normalized_records(corpus: Corpus) -> Iterator[dict[str, object]]:
    seen_ids: set[str] = set()
    for path in source_files(corpus.source):
        with path.open(encoding="utf-8") as source_file:
            records = json.load(source_file)
        if not isinstance(records, list):
            raise ValueError(f"{path}: expected a top-level JSON array")

        for index, value in enumerate(records):
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{index}: expected an object")
            record = dict(value)
            normalize_record(record, path, index)
            record.setdefault("id", f"{corpus.name}/{path.name}:{index}")
            validate_record(record, path, index)
            record_id = str(record["id"])
            if record_id in seen_ids:
                raise ValueError(f"{path}:{index}: duplicate id {record_id}")
            seen_ids.add(record_id)
            yield record


def normalize_record(
    record: dict[str, object],
    path: Path,
    index: int,
) -> None:
    if "title" not in record and isinstance(record.get("rhythmic"), str):
        record["title"] = record["rhythmic"]
    if "format" not in record:
        paragraphs = record.get("paragraphs")
        if not isinstance(paragraphs, list) or not all(
            isinstance(paragraph, str) for paragraph in paragraphs
        ):
            raise ValueError(f"{path}:{index}: invalid paragraphs")
        sentence_lengths = [
            length
            for paragraph in paragraphs
            for fragment in SENTENCE_SEPARATOR.split(paragraph)
            if (length := han_character_count(fragment)) > 0
        ]
        if not sentence_lengths:
            raise ValueError(f"{path}:{index}: no poem sentences found")
        uniform_length = (
            sentence_lengths[0]
            if len(set(sentence_lengths)) == 1
            else None
        )
        record["format"] = {
            "sentence_count": len(sentence_lengths),
            "sentence_lengths": sentence_lengths,
            "uniform_sentence_length": uniform_length,
        }


def han_character_count(text: str) -> int:
    return sum(
        character == "\u3007"
        or "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
        or "\U00020000" <= character <= "\U0002ee5f"
        or "\U00030000" <= character <= "\U000323af"
        for character in text
    )


def validate_record(
    record: dict[str, object],
    path: Path,
    index: int,
) -> None:
    location = f"{path}:{index}"
    for field in ("id", "title", "author"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError(f"{location}: invalid {field}")

    paragraphs = record.get("paragraphs")
    if not isinstance(paragraphs, list) or not all(
        isinstance(paragraph, str) for paragraph in paragraphs
    ):
        raise ValueError(f"{location}: invalid paragraphs")

    poem_format = record.get("format")
    if not isinstance(poem_format, dict):
        raise ValueError(f"{location}: missing format")
    sentence_count = poem_format.get("sentence_count")
    sentence_lengths = poem_format.get("sentence_lengths")
    uniform_length = poem_format.get("uniform_sentence_length")
    if not isinstance(sentence_count, int) or sentence_count < 1:
        raise ValueError(f"{location}: invalid sentence_count")
    if not isinstance(sentence_lengths, list) or not all(
        isinstance(length, int) and length > 0 for length in sentence_lengths
    ):
        raise ValueError(f"{location}: invalid sentence_lengths")
    if len(sentence_lengths) != sentence_count:
        raise ValueError(f"{location}: sentence count mismatch")
    if uniform_length is not None and (
        not isinstance(uniform_length, int)
        or uniform_length < 1
        or any(length != uniform_length for length in sentence_lengths)
    ):
        raise ValueError(f"{location}: inconsistent uniform sentence length")


def build_corpus(corpus: Corpus, output_path: Path) -> int:
    count = 0
    with output_path.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            compresslevel=9,
            mtime=0,
        ) as compressed_output:
            for record in normalized_records(corpus):
                compressed_output.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                )
                compressed_output.write(b"\n")
                count += 1
    return count


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release(version: str) -> dict[str, object]:
    if not version:
        raise ValueError("Version must not be empty")

    if DIST_DIRECTORY.exists():
        shutil.rmtree(DIST_DIRECTORY)
    DIST_DIRECTORY.mkdir()

    corpus_manifest: dict[str, object] = {}
    total_poems = 0
    for corpus in CORPORA:
        output_path = DIST_DIRECTORY / f"{corpus.name}.jsonl.gz"
        poem_count = build_corpus(corpus, output_path)
        total_poems += poem_count
        corpus_manifest[corpus.name] = {
            "asset": output_path.name,
            "poem_count": poem_count,
            "compressed_bytes": output_path.stat().st_size,
            "sha256": sha256(output_path),
        }
        print(
            f"{corpus.name}: {poem_count:,} poems, "
            f"{output_path.stat().st_size / 1024 / 1024:.1f} MiB"
        )

    manifest = {
        "version": version,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_poems": total_poems,
        "corpora": corpus_manifest,
    }
    serialized_manifest = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    MANIFEST_PATH.write_text(serialized_manifest, encoding="utf-8")
    (DIST_DIRECTORY / "manifest.json").write_text(
        serialized_manifest,
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    manifest = build_release(args.version)
    print(f"Built {manifest['total_poems']:,} poems")


if __name__ == "__main__":
    main()
