import json
from pathlib import Path

import pytest

from scripts.audit_song_reclassifications import (
    audit_song_reclassifications,
    record_fingerprint,
)


def write_records(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )


def test_audits_removed_qss_record_and_retained_qsc_record(
    tmp_path: Path,
) -> None:
    qsc_directory = tmp_path / "qsc"
    qss_directory = tmp_path / "qss"
    qsc_directory.mkdir()
    qss_directory.mkdir()
    retained = {
        "title": "渔父词",
        "author": "作者",
        "paragraphs": ["一叶舟。"],
    }
    removed = {
        "title": "渔父词  其一",
        "author": "作者",
        "paragraphs": ["一葉舟。"],
    }
    write_records(qsc_directory / "00000.json", [retained])
    write_records(qss_directory / "000000.json", [])
    manifest = {
        "removed_from_qss": 1,
        "reclassifications": [
            {
                "from_corpus": "qss",
                "to_corpus": "qsc",
                "from_fingerprint": record_fingerprint(removed),
                "retained_fingerprint": record_fingerprint(retained),
                "retained_file": "00000.json",
                "retained_index": 0,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    assert audit_song_reclassifications(
        manifest_path,
        qsc_directory,
        qss_directory,
    ) == 1


def test_rejects_reclassification_still_present_in_qss(
    tmp_path: Path,
) -> None:
    qsc_directory = tmp_path / "qsc"
    qss_directory = tmp_path / "qss"
    qsc_directory.mkdir()
    qss_directory.mkdir()
    retained = {
        "title": "渔父词",
        "author": "作者",
        "paragraphs": ["一叶舟。"],
    }
    removed = {
        "title": "渔父词  其一",
        "author": "作者",
        "paragraphs": ["一葉舟。"],
    }
    write_records(qsc_directory / "00000.json", [retained])
    write_records(qss_directory / "000000.json", [removed])
    manifest = {
        "removed_from_qss": 1,
        "reclassifications": [
            {
                "from_corpus": "qss",
                "to_corpus": "qsc",
                "from_fingerprint": record_fingerprint(removed),
                "retained_fingerprint": record_fingerprint(retained),
                "retained_file": "00000.json",
                "retained_index": 0,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="still present in QSS"):
        audit_song_reclassifications(
            manifest_path,
            qsc_directory,
            qss_directory,
        )


def test_audits_removed_qsc_record_and_retained_qss_record(
    tmp_path: Path,
) -> None:
    qsc_directory = tmp_path / "qsc"
    qss_directory = tmp_path / "qss"
    qsc_directory.mkdir()
    qss_directory.mkdir()
    removed = {
        "title": "失调名",
        "author": "作者",
        "paragraphs": ["松风明月。"],
    }
    retained = {
        "title": "诗一首",
        "author": "作者",
        "paragraphs": ["松風明月。"],
    }
    write_records(qsc_directory / "00000.json", [])
    write_records(qss_directory / "000000.json", [retained])
    manifest = {
        "removed_from_qss": 0,
        "removed_from_qsc": 1,
        "reclassifications": [
            {
                "from_corpus": "qsc",
                "to_corpus": "qss",
                "from_fingerprint": record_fingerprint(removed),
                "retained_fingerprint": record_fingerprint(retained),
                "retained_file": "000000.json",
                "retained_index": 0,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    assert audit_song_reclassifications(
        manifest_path,
        qsc_directory,
        qss_directory,
    ) == 1


def test_rejects_stale_retained_index(tmp_path: Path) -> None:
    qsc_directory = tmp_path / "qsc"
    qss_directory = tmp_path / "qss"
    qsc_directory.mkdir()
    qss_directory.mkdir()
    retained = {
        "title": "渔父词",
        "author": "作者",
        "paragraphs": ["一叶舟。"],
    }
    other = {
        "title": "另一首",
        "author": "作者",
        "paragraphs": ["不同内容。"],
    }
    removed = {
        "title": "渔父词  其一",
        "author": "作者",
        "paragraphs": ["一葉舟。"],
    }
    write_records(qsc_directory / "00000.json", [other, retained])
    write_records(qss_directory / "000000.json", [])
    manifest = {
        "removed_from_qss": 1,
        "reclassifications": [
            {
                "from_corpus": "qss",
                "to_corpus": "qsc",
                "from_fingerprint": record_fingerprint(removed),
                "retained_fingerprint": record_fingerprint(retained),
                "retained_file": "00000.json",
                "retained_index": 0,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="retained index does not match"):
        audit_song_reclassifications(
            manifest_path,
            qsc_directory,
            qss_directory,
        )
