import json
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.build_release import (
    COUNTED_CHARACTER,
    calculate_poem_format,
    content_id,
)


ROOT = Path(__file__).parents[1]


def test_hwlcs_cleanup_receipts_match_current_records() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    log = json.loads(
        (ROOT / "editorial/hwlcs-cleanup.json").read_text(encoding="utf-8")
    )
    by_id = {content_id("hwlcs", record): record for record in records}
    evidence_urls = {witness["url"] for witness in log["witnesses"]}

    assert len(by_id) == len(records) == log["poem_count"]
    assert len(records) == (
        log["baseline"]["poem_count"] - len(log["duplicate_removals"])
    )
    for witness in log["witnesses"]:
        assert witness["url"] == (
            f"https://zh.wikisource.org/w/index.php?oldid={witness['revision']}"
        )
        assert len(witness["sha256"]) == 64
    for correction in log["corrections"]:
        assert (
            content_id("hwlcs", correction["before"])
            == correction["source_id"]
        )
        assert (
            by_id[content_id("hwlcs", correction["after"])]
            == correction["after"]
        )
        assert set(correction["evidence"]) <= evidence_urls
    for removal in log["duplicate_removals"]:
        assert content_id("hwlcs", removal["record"]) == removal["source_id"]
        assert removal["source_id"] not in by_id
        assert removal["kept_id"] in by_id
        assert removal["evidence"]
        assert set(removal["evidence"]) <= evidence_urls
    for review in log["retained_reviews"]:
        for record in review["records"]:
            assert by_id[record["id"]]["title"] == record["title"]
            assert by_id[record["id"]]["author"] == record["author"]
        assert set(review["evidence"]) <= evidence_urls


def test_hwlcs_has_consistent_format_without_known_artifacts() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    normalized_texts = []

    for record in records:
        assert record["format"] == calculate_poem_format(
            record["paragraphs"], "hwlcs"
        )
        values = [record["title"], record["author"], *record["paragraphs"]]
        assert all(value == value.strip() for value in values)
        text = "\n".join(values)
        assert not any(
            unicodedata.category(character) == "Co" for character in text
        )
        assert all(marker not in text for marker in ("�", "①", "（○同上）", "∶"))
        normalized_texts.append(
            "".join(COUNTED_CHARACTER.findall(
                "".join(record["paragraphs"])
            ))
        )

    assert len(set(normalized_texts)) == len(records)


def test_ban_jieyu_uses_yuefu_title_and_complete_edition_text() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    poems = [record for record in records if record["author"] == "班婕妤"]

    assert len(poems) == 1
    assert poems[0]["title"] == "怨歌行"
    assert poems[0]["paragraphs"] == [
        "新裂齐纨素，鲜洁如霜雪。",
        "裁为合欢扇，团团似明月。",
        "出入君怀袖，动摇微风发。",
        "常恐秋节至，凉飙夺炎热。",
        "弃捐箧笥中，恩情中道绝。",
    ]


def test_ri_chu_ru_does_not_split_zi_huang() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    poem = next(record for record in records if record["title"] == "日出入")

    assert poem["paragraphs"][-1] == "訾黄其何不徕下！"
    assert poem["format"]["sentence_count"] == 13
    assert poem["format"]["sentence_lengths"][-1] == 7


def test_hwlcs_preserves_documented_edition_readings() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    by_author_title = {
        (record["author"], record["title"]): record for record in records
    }
    readings = [
        ("曹植", "鼙舞歌五首·其二·灵芝篇", ["灵芝生王地", "犯罪以亡形"]),
        (
            "曹植", "鼙舞歌五首·其四·精微篇",
            ["身没垂功名", "妾愿以身代", "归聘为夫人", "刑措民无枉"],
        ),
        ("萧子显", "乌栖曲应令三首·其一", ["琥珀龙"]),
        ("萧子显", "乌栖曲应令三首·其二", ["金壶夜水", "莫持赊用"]),
        ("鲍照", "拟古诗八首·其二", ["耻受聊城功", "卷袠奉卢弓"]),
    ]
    for author, title, phrases in readings:
        text = "".join(by_author_title[(author, title)]["paragraphs"])
        assert all(phrase in text for phrase in phrases)


def test_hwlcs_preserves_attested_refrains_and_short_fragments() -> None:
    records = json.loads(
        (ROOT / "raw/hwlcs/hwlcs.json").read_text(encoding="utf-8")
    )
    songs = [
        record for record in records
        if record["author"] == "陆机"
        and record["title"].startswith("百年歌十首")
    ]
    assert len(songs) == 10
    for song in songs[:6]:
        assert Counter(song["paragraphs"])["清酒将炙奈乐何。"] == 2
    song = next(
        record for record in records
        if record["author"] == "谢灵运" and record["title"] == "上留田行"
    )
    assert len(song["paragraphs"]) == 20
    assert Counter(song["paragraphs"])["薄游出彼东道，上留田。"] == 2
    assert sum(
        len(COUNTED_CHARACTER.findall("".join(record["paragraphs"]))) <= 8
        for record in records
    ) == 10
