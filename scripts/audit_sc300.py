from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from scripts.build_release import calculate_poem_format


ROOT = Path(__file__).parents[1]
DEFAULT_CORPUS_PATH = ROOT / "raw" / "sc300" / "sc300.json"
DEFAULT_LOCK_PATH = ROOT / "source-locks" / "sc300.json"
API_URL = "https://zh.wikisource.org/w/api.php"
HEADING_MARKER = '<div class="mw-heading mw-heading2">'
POEM_PATTERN = re.compile(r'<div class="poem">(.*?)</div>', re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
SUPERSCRIPT_PATTERN = re.compile(r"<sup\b.*?</sup>", re.DOTALL)
BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^(.*?)[（(]([^（）()]+)[）)]$")


def api_request(parameters: dict[str, object]) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            **parameters,
            "format": "json",
            "formatversion": 2,
        }
    )
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "shici-data-sc300-audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Wikisource returned an invalid response")
    return payload


def text_content(value: str) -> str:
    return html.unescape(TAG_PATTERN.sub("", value)).strip()


def poem_paragraphs(value: str) -> list[str]:
    value = SUPERSCRIPT_PATTERN.sub("", value)
    value = BREAK_PATTERN.sub("\n", value)
    value = TAG_PATTERN.sub("", value)
    value = html.unescape(value)
    paragraphs = [
        re.sub(r"[ \t\r\n]+", " ", paragraph).strip()
        for paragraph in value.split("\n")
    ]
    return [paragraph for paragraph in paragraphs if paragraph]


def extract_records(parse_payload: dict[str, Any]) -> list[dict[str, object]]:
    parsed = parse_payload.get("parse")
    if not isinstance(parsed, dict):
        raise ValueError("Wikisource response is missing parse data")
    sections = parsed.get("sections")
    rendered_html = parsed.get("text")
    if not isinstance(sections, list) or not isinstance(rendered_html, str):
        raise ValueError("Wikisource response has invalid sections or text")

    blocks = rendered_html.split(HEADING_MARKER)[1:]
    if len(blocks) != len(sections):
        raise ValueError(
            "Wikisource heading count does not match its section count"
        )

    records: list[dict[str, object]] = []
    for index, (section, block) in enumerate(zip(sections, blocks)):
        if not isinstance(section, dict) or not isinstance(
            section.get("line"), str
        ):
            raise ValueError(f"Wikisource section {index} has no heading")
        heading = text_content(section["line"])
        heading_match = HEADING_PATTERN.fullmatch(heading)
        if heading_match is None:
            raise ValueError(
                f"Wikisource section {index} has an invalid heading: {heading}"
            )
        title, author = (
            value.strip() for value in heading_match.groups()
        )

        poem_match = POEM_PATTERN.search(block)
        if poem_match is None:
            raise ValueError(
                f"Wikisource section {index} has no poem body: {heading}"
            )
        records.append(
            {
                "title": title,
                "author": author,
                "paragraphs": poem_paragraphs(poem_match.group(1)),
            }
        )
    return records


def apply_metadata_overrides(
    records: list[dict[str, object]],
    overrides: object,
) -> None:
    if not isinstance(overrides, list):
        raise ValueError("metadata_overrides must be a list")
    for override in overrides:
        if not isinstance(override, dict):
            raise ValueError("metadata override must be an object")
        index = override.get("index")
        field = override.get("field")
        source_value = override.get("source_value")
        value = override.get("value")
        if (
            not isinstance(index, int)
            or not isinstance(field, str)
            or not isinstance(source_value, str)
            or not isinstance(value, str)
        ):
            raise ValueError("metadata override has invalid fields")
        if index < 0 or index >= len(records):
            raise ValueError(f"metadata override index is invalid: {index}")
        if records[index].get(field) != source_value:
            raise ValueError(
                f"metadata override source mismatch at record {index}: "
                f"expected {source_value!r}, got {records[index].get(field)!r}"
            )
        records[index][field] = value


def apply_paragraph_splits(
    records: list[dict[str, object]],
    splits: object,
) -> None:
    if not isinstance(splits, list):
        raise ValueError("paragraph_splits must be a list")
    for split in splits:
        if not isinstance(split, dict):
            raise ValueError("paragraph split must be an object")
        index = split.get("index")
        paragraph_index = split.get("paragraph_index")
        separator = split.get("separator")
        if (
            not isinstance(index, int)
            or not isinstance(paragraph_index, int)
            or not isinstance(separator, str)
            or not separator
        ):
            raise ValueError("paragraph split has invalid fields")
        if index < 0 or index >= len(records):
            raise ValueError(f"paragraph split record is invalid: {index}")
        paragraphs = records[index].get("paragraphs")
        if not isinstance(paragraphs, list) or not all(
            isinstance(paragraph, str) for paragraph in paragraphs
        ):
            raise ValueError(f"record {index} has invalid paragraphs")
        if paragraph_index < 0 or paragraph_index >= len(paragraphs):
            raise ValueError(
                f"paragraph split index is invalid: {paragraph_index}"
            )
        parts = paragraphs[paragraph_index].split(separator)
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"record {index} paragraph {paragraph_index} does not "
                "contain exactly one split separator"
            )
        paragraphs[paragraph_index : paragraph_index + 1] = parts


def validate_revision(lock: dict[str, object]) -> None:
    revision_id = lock.get("revision_id")
    if not isinstance(revision_id, int):
        raise ValueError("source lock has no revision_id")
    response = api_request(
        {
            "action": "query",
            "prop": "revisions",
            "revids": revision_id,
            "rvprop": "ids|timestamp|sha1",
        }
    )
    pages = response.get("query", {}).get("pages")
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError("Wikisource did not return the pinned revision")
    page = pages[0]
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or len(revisions) != 1:
        raise ValueError("Wikisource did not return revision metadata")
    revision = revisions[0]
    expected = {
        "pageid": lock.get("page_id"),
        "revid": revision_id,
        "timestamp": lock.get("revision_timestamp"),
        "sha1": lock.get("revision_sha1"),
    }
    actual = {
        "pageid": page.get("pageid"),
        "revid": revision.get("revid"),
        "timestamp": revision.get("timestamp"),
        "sha1": revision.get("sha1"),
    }
    if actual != expected:
        raise ValueError(
            f"Wikisource revision metadata mismatch: expected {expected}, "
            f"got {actual}"
        )


def fetch_source_records(lock: dict[str, object]) -> list[dict[str, object]]:
    revision_id = lock.get("revision_id")
    variant = lock.get("variant")
    if not isinstance(revision_id, int) or not isinstance(variant, str):
        raise ValueError("source lock has invalid revision or variant")
    response = api_request(
        {
            "action": "parse",
            "oldid": revision_id,
            "prop": "text|sections",
            "variant": variant,
        }
    )
    records = extract_records(response)
    expected_count = lock.get("record_count")
    if len(records) != expected_count:
        raise ValueError(
            f"Wikisource record count mismatch: expected {expected_count}, "
            f"got {len(records)}"
        )
    apply_metadata_overrides(
        records,
        lock.get("metadata_overrides", []),
    )
    apply_paragraph_splits(
        records,
        lock.get("paragraph_splits", []),
    )
    return records


def audit_sc300(corpus_path: Path, lock_path: Path) -> tuple[int, int]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    local_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or not isinstance(local_records, list):
        raise ValueError("invalid source lock or SC300 corpus")

    validate_revision(lock)
    source_records = fetch_source_records(lock)
    if len(local_records) != len(source_records):
        raise ValueError(
            f"local record count mismatch: expected {len(source_records)}, "
            f"got {len(local_records)}"
        )

    mismatches: list[str] = []
    for index, (local, source) in enumerate(
        zip(local_records, source_records)
    ):
        for field in ("title", "author", "paragraphs"):
            if local.get(field) != source[field]:
                mismatches.append(
                    f"record {index} {field}: expected {source[field]!r}, "
                    f"got {local.get(field)!r}"
                )
        paragraphs = local.get("paragraphs")
        if isinstance(paragraphs, list) and all(
            isinstance(paragraph, str) for paragraph in paragraphs
        ):
            expected_format = calculate_poem_format(paragraphs, "sc300")
            if local.get("format") != expected_format:
                mismatches.append(
                    f"record {index} format: expected {expected_format!r}, "
                    f"got {local.get('format')!r}"
                )
    if mismatches:
        detail = "\n".join(mismatches[:20])
        suffix = (
            ""
            if len(mismatches) <= 20
            else f"\n... and {len(mismatches) - 20} more"
        )
        raise ValueError(f"SC300 audit failed:\n{detail}{suffix}")
    revision_id = lock["revision_id"]
    if not isinstance(revision_id, int):
        raise ValueError("source lock has no revision_id")
    return len(local_records), revision_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit SC300 against its pinned Wikisource revision."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_PATH,
    )
    parser.add_argument(
        "--source-lock",
        type=Path,
        default=DEFAULT_LOCK_PATH,
    )
    arguments = parser.parse_args()
    record_count, revision_id = audit_sc300(
        arguments.corpus,
        arguments.source_lock,
    )
    print(
        f"SC300 audit passed: {record_count} records match Wikisource "
        f"revision {revision_id}."
    )


if __name__ == "__main__":
    main()
