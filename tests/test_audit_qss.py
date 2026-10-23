import pytest

from scripts.audit_qss import (
    apply_metadata_repairs,
    apply_paragraph_repairs,
    cleanup_removal_locations,
    unresolved_counts,
)


def test_validates_qss_cleanup_removals() -> None:
    records = {
        "000000.json": [
            {
                "title": "完整",
                "author": "作者",
                "paragraphs": ["天地玄黃。"],
                "_source_index": 0,
            },
            {
                "title": "完整",
                "author": "作者",
                "paragraphs": ["天地玄黃。"],
                "_source_index": 1,
            },
            {
                "title": "空篇",
                "author": "作者",
                "paragraphs": [],
                "_source_index": 2,
            },
            {
                "title": "殘篇",
                "author": "作者",
                "paragraphs": ["□□，□□。"],
                "_source_index": 3,
            },
        ]
    }
    changes = [
        {
            "source_file": "000000.json",
            "source_index": 1,
            "kind": "exact_duplicate",
            "duplicate_of_file": "000000.json",
            "duplicate_of_index": 0,
        },
        {
            "source_file": "000000.json",
            "source_index": 2,
            "kind": "empty_text",
        },
        {
            "source_file": "000000.json",
            "source_index": 3,
            "kind": "all_placeholders",
        },
    ]

    assert cleanup_removal_locations(records, changes) == {
        ("000000.json", 1),
        ("000000.json", 2),
        ("000000.json", 3),
    }


def test_rejects_nonduplicate_qss_removal() -> None:
    records = {
        "000000.json": [
            {
                "title": "其一",
                "author": "作者",
                "paragraphs": ["天地玄黃。"],
                "_source_index": 0,
            },
            {
                "title": "其二",
                "author": "作者",
                "paragraphs": ["宇宙洪荒。"],
                "_source_index": 1,
            },
        ]
    }

    with pytest.raises(ValueError, match="not a duplicate"):
        cleanup_removal_locations(
            records,
            [
                {
                    "source_file": "000000.json",
                    "source_index": 1,
                    "kind": "exact_duplicate",
                    "duplicate_of_file": "000000.json",
                    "duplicate_of_index": 0,
                }
            ],
        )


def test_counts_qss_unresolved_defects() -> None:
    records = {
        "000000.json": [
            {
                "title": "闕□",
                "author": "作□",
                "paragraphs": ["天地□□。"],
            }
        ]
    }

    assert unresolved_counts(records) == {
        "lacuna_records": 1,
        "lacuna_occurrences": 2,
        "lacuna_at_least_25_percent": 1,
        "author_placeholder_records": 1,
        "title_placeholder_records": 1,
    }


def test_applies_qss_metadata_repairs() -> None:
    records = {
        "000000.json": [
            {
                "title": "贈□道人",
                "author": "□韞",
                "paragraphs": ["天地玄黃。"],
                "_source_index": 0,
            }
        ]
    }

    apply_metadata_repairs(
        records,
        [
            {
                "source_file": "000000.json",
                "source_index": 0,
                "source_value": "□韞",
                "value": "某韞",
            }
        ],
        "author",
    )
    apply_metadata_repairs(
        records,
        [
            {
                "source_file": "000000.json",
                "source_index": 0,
                "source_value": "贈□道人",
                "value": "贈某道人",
            }
        ],
        "title",
    )

    assert records["000000.json"][0]["author"] == "某韞"
    assert records["000000.json"][0]["title"] == "贈某道人"


def test_applies_qss_paragraph_repairs() -> None:
    records = {
        "000000.json": [
            {
                "title": "殘篇",
                "author": "作者",
                "paragraphs": ["天地□黃。"],
                "_source_index": 0,
            }
        ]
    }

    apply_paragraph_repairs(
        records,
        [
            {
                "source_file": "000000.json",
                "source_index": 0,
                "paragraph_index": 0,
                "source_value": "天地□黃。",
                "value": "天地玄黃。",
            }
        ],
    )

    assert records["000000.json"][0]["paragraphs"] == ["天地玄黃。"]


def test_rejects_qss_paragraph_repair_source_drift() -> None:
    records = {
        "000000.json": [
            {
                "title": "殘篇",
                "author": "作者",
                "paragraphs": ["天地□黃。"],
                "_source_index": 0,
            }
        ]
    }

    with pytest.raises(ValueError, match="paragraph repair mismatch"):
        apply_paragraph_repairs(
            records,
            [
                {
                    "source_file": "000000.json",
                    "source_index": 0,
                    "paragraph_index": 0,
                    "source_value": "宇宙□荒。",
                    "value": "宇宙洪荒。",
                }
            ],
        )
