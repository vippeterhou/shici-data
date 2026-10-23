import pytest

from scripts.audit_qsc import join_suite_record, validate_qsc_quality


def test_joins_qsc_suite_stanzas() -> None:
    records = [
        {
            "title": "九张机",
            "author": "无名氏",
            "paragraphs": [
                "一张机。",
                "织梭光景去如飞。",
                "兰房夜永愁无寐。",
                "呕呕轧轧，织成春恨，留著待郎归。",
            ],
        },
        {
            "title": "九张机",
            "author": "无名氏",
            "paragraphs": [
                "两张机。",
                "月明人静漏声稀。",
                "千丝万缕相萦系。",
                "织成一段，回纹锦字。",
                "将去寄呈伊。",
            ],
        },
    ]

    assert join_suite_record(records, {}) == {
        "title": "九张机",
        "author": "无名氏",
        "paragraphs": [
            "一张机。",
            "织梭光景去如飞。",
            "兰房夜永愁无寐，呕呕轧轧，织成春恨，留著待郎归。",
            "两张机。",
            "月明人静漏声稀。",
            "千丝万缕相萦系，织成一段，回纹锦字，将去寄呈伊。",
        ],
    }


@pytest.mark.parametrize(
    ("author", "paragraph", "message"),
    [
        ("作者1", "天地玄黄。", "numeric author suffix"),
        ("作者", "天地�黄。", "replacement character"),
    ],
)
def test_rejects_qsc_quality_defects(
    author: str,
    paragraph: str,
    message: str,
) -> None:
    records = {
        "00000.json": [
            {
                "title": "测试",
                "author": author,
                "paragraphs": [paragraph],
                "format": {
                    "sentence_count": 1,
                    "sentence_lengths": [4],
                    "uniform_sentence_length": 4,
                },
            }
        ]
    }

    with pytest.raises(ValueError, match=message):
        validate_qsc_quality(records)


def test_validates_expected_unresolved_qsc_defects() -> None:
    records = {
        "00000.json": [
            {
                "title": "□□",
                "author": "张□",
                "paragraphs": ["（上缺）□□□□天地。", "余有缺词文。"],
            }
        ]
    }
    expected = {
        "lacuna_records": 1,
        "lacuna_occurrences": 4,
        "lacuna_at_least_25_percent": 1,
        "partial_missing_text_records": 1,
        "explicit_truncation_records": 1,
        "author_placeholder_records": 1,
        "title_placeholder_records": 1,
    }

    validate_qsc_quality(records, expected)

    with pytest.raises(ValueError, match="unresolved-defect counts changed"):
        validate_qsc_quality(
            records,
            {**expected, "lacuna_occurrences": 5},
        )
