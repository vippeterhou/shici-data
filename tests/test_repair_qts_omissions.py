from scripts.repair_qts_omissions import (
    aligned_chunks,
    corroborated_missing_positions,
    longest_common_subsequence_positions,
    merge_paragraphs,
    serialize_records,
    subsequence_positions,
)


def test_finds_ordered_subsequence_positions() -> None:
    assert subsequence_positions(
        ["first", "third", "fifth"],
        ["first", "second", "third", "fourth", "fifth"],
    ) == [0, 2, 4]
    assert subsequence_positions(
        ["first", "missing"],
        ["first", "second"],
    ) is None


def test_merges_missing_sentences_and_preserves_existing_text() -> None:
    current = ["甲，乙。丙，", "庚，辛。"]
    complete = ["甲，乙。丙，丁。戊，己。", "庚，辛。"]

    assert merge_paragraphs(current, complete, lambda value: value) == [
        "甲，乙。丙，丁。戊，己。",
        "庚，辛。",
    ]


def test_merges_only_selected_missing_sentences() -> None:
    assert merge_paragraphs(
        ["甲，丙，戊。"],
        ["甲，乙。丙，丁。戊。"],
        lambda value: value,
        {1},
    ) == ["甲，乙。丙，戊。"]


def test_corroborates_exact_missing_sentences_with_variant_elsewhere() -> None:
    complete = ["甲", "乙", "丙", "丁", "戊"]
    witness = ["甲", "異", "丙", "丁", "戊"]

    assert longest_common_subsequence_positions(complete, witness) == {
        0,
        2,
        3,
        4,
    }
    assert corroborated_missing_positions(
        [0, 2, 4],
        complete,
        [witness],
    ) == {3}


def test_rejects_witness_without_surviving_sentence_anchor() -> None:
    assert corroborated_missing_positions(
        [0],
        ["甲", "乙", "丙"],
        [["乙", "丙"]],
    ) == set()


def test_attaches_punctuation_only_fragments_to_existing_sentence() -> None:
    assert aligned_chunks(
        "甲，。乙。",
        lambda value: value.replace("，", "").replace("。", ""),
    ) == ["甲，。", "乙。"]


def test_colon_and_ascii_semicolon_create_alignment_chunks() -> None:
    assert aligned_chunks("乱曰：甲;乙。", lambda value: value) == [
        "乱曰：",
        "甲;",
        "乙。",
    ]


def test_serializes_qts_layout() -> None:
    records = [
        {
            "title": "題",
            "author": "作者",
            "paragraphs": ["甲，乙。"],
            "format": {
                "sentence_count": 2,
                "sentence_lengths": [1, 1],
                "uniform_sentence_length": 1,
            },
        }
    ]

    assert serialize_records(records) == (
        "[\n"
        "  {\n"
        '    \"title\": \"題\",\n'
        '    \"author\": \"作者\",\n'
        '    \"paragraphs\": [\n'
        '      \"甲，乙。\"\n'
        "    ],\n"
        '    \"format\": {\n'
        '      \"sentence_count\": 2,\n'
        '      \"sentence_lengths\": [1, 1],\n'
        '      \"uniform_sentence_length\": 1\n'
        "    }\n"
        "  }\n"
        "]\n"
    )
