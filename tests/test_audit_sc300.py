from scripts.audit_sc300 import (
    apply_metadata_overrides,
    apply_paragraph_splits,
    extract_records,
)


def test_extracts_wikisource_poems() -> None:
    payload = {
        "parse": {
            "sections": [
                {"line": "<b>词牌</b>（作者）"},
                {"line": "另一词牌 (另一作者)"},
            ],
            "text": (
                '<div class="mw-heading mw-heading2"><h2>词牌（作者）</h2>'
                "</div>"
                '<div class="poem"><p>上句。<br />下句。</p></div>'
                '<div class="mw-heading mw-heading2">'
                "<h2>另一词牌 (另一作者)</h2></div>"
                '<div class="poem"><p>前段。<br /><br />后段。</p></div>'
            ),
        }
    }

    assert extract_records(payload) == [
        {
            "title": "词牌",
            "author": "作者",
            "paragraphs": ["上句。", "下句。"],
        },
        {
            "title": "另一词牌",
            "author": "另一作者",
            "paragraphs": ["前段。", "后段。"],
        },
    ]


def test_applies_explicit_metadata_override() -> None:
    records = [
        {
            "title": "六幺令",
            "author": "晏几道",
            "paragraphs": ["绿阴春尽。"],
        }
    ]

    apply_metadata_overrides(
        records,
        [
            {
                "index": 0,
                "field": "title",
                "source_value": "六幺令",
                "value": "六么令",
            }
        ],
    )

    assert records[0]["title"] == "六么令"


def test_applies_explicit_paragraph_split() -> None:
    records = [
        {
            "title": "词牌",
            "author": "作者",
            "paragraphs": ["上阕。　　下阕。"],
        }
    ]

    apply_paragraph_splits(
        records,
        [
            {
                "index": 0,
                "paragraph_index": 0,
                "separator": "　　",
            }
        ],
    )

    assert records[0]["paragraphs"] == ["上阕。", "下阕。"]
