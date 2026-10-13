from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from scripts.build_release import calculate_poem_format


ROOT = Path(__file__).parents[1]
QTS_DIRECTORY = ROOT / "raw" / "qts"
SENTENCE_CHUNK = re.compile(r".*?[，。！？；：:;]|.+$")
NON_HAN_CHARACTER = re.compile(
    r"[^\u3400-\u9fff\U00020000-\U000323af〇□]"
)
KNOWN_VARIANTS = str.maketrans(
    {
        "祗": "祇",
        "旂": "旗",
        "栢": "柏",
        "裏": "里",
        "衞": "衛",
        "秪": "只",
        "櫂": "棹",
        "綵": "彩",
        "羣": "群",
        "篷": "蓬",
        "后": "後",
        "於": "于",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair QTS omissions corroborated by CText/ZZU or "
            "CText/chinese-poetry."
        )
    )
    parser.add_argument(
        "--ctext-directory",
        type=Path,
        required=True,
        help="Directory containing CText_JSON_cht/zh_NNNN.json files.",
    )
    parser.add_argument(
        "--zzu-directory",
        type=Path,
        required=True,
        help="Directory containing ZZU_JSON_chs/zhs_NNNN.json files.",
    )
    parser.add_argument(
        "--split-directory",
        type=Path,
        required=True,
        help="Directory containing chinese-poetry poet.tang.*.json files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write repairs. Without this flag, only report the repair scope.",
    )
    return parser.parse_args()


def build_normalizer() -> Callable[[str], str]:
    try:
        from opencc import OpenCC
    except ImportError as error:
        raise SystemExit(
            "opencc is required: install the project audit environment first"
        ) from error

    converter = OpenCC("t2s")

    def normalize(value: str) -> str:
        standardized = value.translate(KNOWN_VARIANTS)
        return NON_HAN_CHARACTER.sub("", converter.convert(standardized))

    return normalize


def sentence_chunks(paragraph: str) -> list[str]:
    return [
        match.group()
        for match in SENTENCE_CHUNK.finditer(paragraph)
        if match.group()
    ]


def aligned_chunks(
    paragraph: str,
    normalize: Callable[[str], str],
) -> list[str]:
    chunks: list[str] = []
    prefix = ""
    for chunk in sentence_chunks(paragraph):
        if normalize(chunk):
            chunks.append(prefix + chunk)
            prefix = ""
        elif chunks:
            chunks[-1] += chunk
        else:
            prefix += chunk
    if prefix:
        if chunks:
            chunks[-1] += prefix
        else:
            chunks.append(prefix)
    return chunks


def normalized_sequence(
    paragraphs: Iterable[str],
    normalize: Callable[[str], str],
) -> list[str]:
    return [
        normalize(chunk)
        for paragraph in paragraphs
        for chunk in aligned_chunks(paragraph, normalize)
        if normalize(chunk)
    ]


def subsequence_positions(
    current: list[str],
    complete: list[str],
) -> list[int] | None:
    positions: list[int] = []
    complete_index = 0
    for sentence in current:
        while (
            complete_index < len(complete)
            and complete[complete_index] != sentence
        ):
            complete_index += 1
        if complete_index == len(complete):
            return None
        positions.append(complete_index)
        complete_index += 1
    return positions


def longest_common_subsequence_positions(
    complete: list[str],
    witness: list[str],
) -> set[int]:
    complete_length = len(complete)
    witness_length = len(witness)
    lengths = [
        [0] * (witness_length + 1)
        for _ in range(complete_length + 1)
    ]
    for complete_index in range(complete_length - 1, -1, -1):
        for witness_index in range(witness_length - 1, -1, -1):
            if complete[complete_index] == witness[witness_index]:
                lengths[complete_index][witness_index] = (
                    1 + lengths[complete_index + 1][witness_index + 1]
                )
            else:
                lengths[complete_index][witness_index] = max(
                    lengths[complete_index + 1][witness_index],
                    lengths[complete_index][witness_index + 1],
                )

    positions: set[int] = set()
    complete_index = 0
    witness_index = 0
    while (
        complete_index < complete_length
        and witness_index < witness_length
    ):
        if complete[complete_index] == witness[witness_index]:
            positions.add(complete_index)
            complete_index += 1
            witness_index += 1
        elif (
            lengths[complete_index + 1][witness_index]
            >= lengths[complete_index][witness_index + 1]
        ):
            complete_index += 1
        else:
            witness_index += 1
    return positions


def corroborated_missing_positions(
    current_positions: list[int],
    complete: list[str],
    witnesses: Iterable[list[str]],
) -> set[int]:
    current_position_set = set(current_positions)
    missing_positions = set(range(len(complete))) - current_position_set
    corroborated: set[int] = set()
    minimum_overlap = max(
        len(current_positions),
        math.ceil(len(complete) / 2),
    )
    for witness in witnesses:
        matched_positions = longest_common_subsequence_positions(
            complete, witness
        )
        if (
            len(matched_positions) >= minimum_overlap
            and matched_positions & current_position_set
        ):
            corroborated.update(missing_positions & matched_positions)
    return corroborated


def merge_paragraphs(
    current_paragraphs: list[str],
    complete_paragraphs: list[str],
    normalize: Callable[[str], str],
    insert_positions: set[int] | None = None,
) -> list[str] | None:
    current_chunks = [
        chunk
        for paragraph in current_paragraphs
        for chunk in aligned_chunks(paragraph, normalize)
    ]
    complete_chunk_groups = [
        aligned_chunks(paragraph, normalize)
        for paragraph in complete_paragraphs
    ]
    complete_chunks = [
        chunk for group in complete_chunk_groups for chunk in group
    ]
    positions = subsequence_positions(
        [normalize(chunk) for chunk in current_chunks],
        [normalize(chunk) for chunk in complete_chunks],
    )
    if positions is None or len(complete_chunks) <= len(current_chunks):
        return None

    replacements = dict(zip(positions, current_chunks))
    merged: list[str] = []
    flat_index = 0
    for group in complete_chunk_groups:
        merged_group: list[str] = []
        for chunk in group:
            if flat_index in replacements:
                merged_group.append(replacements[flat_index])
            elif insert_positions is None or flat_index in insert_positions:
                merged_group.append(chunk)
            flat_index += 1
        if merged_group:
            merged.append("".join(merged_group))
    return merged


def record_key(
    record: dict[str, Any],
    normalize: Callable[[str], str],
) -> tuple[str, str]:
    return (
        normalize(str(record.get("title", ""))),
        normalize(str(record.get("author", ""))),
    )


def index_records(
    records: Iterable[dict[str, Any]],
    normalize: Callable[[str], str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        index[record_key(record, normalize)].append(record)
    return index


def load_split_sequences(
    directory: Path,
    normalize: Callable[[str], str],
) -> dict[tuple[str, str], list[list[str]]]:
    sequences: dict[tuple[str, str], list[list[str]]] = defaultdict(list)
    paths = sorted(directory.glob("poet.tang.*.json"))
    if not paths:
        raise ValueError(f"No poet.tang.*.json files found in {directory}")
    for path in paths:
        for record in json.loads(path.read_text(encoding="utf-8")):
            sequences[record_key(record, normalize)].append(
                normalized_sequence(record.get("paragraphs", []), normalize)
            )
    return sequences


def serialize_records(records: list[dict[str, Any]]) -> str:
    lines = ["["]
    for record_index, record in enumerate(records):
        lines.extend(
            [
                "  {",
                f'    "title": {json.dumps(record["title"], ensure_ascii=False)},',
                f'    "author": {json.dumps(record["author"], ensure_ascii=False)},',
                '    "paragraphs": [',
            ]
        )
        paragraphs = record["paragraphs"]
        for paragraph_index, paragraph in enumerate(paragraphs):
            comma = "," if paragraph_index < len(paragraphs) - 1 else ""
            lines.append(
                f"      {json.dumps(paragraph, ensure_ascii=False)}{comma}"
            )
        poem_format = record["format"]
        lines.extend(
            [
                "    ],",
                '    "format": {',
                (
                    '      "sentence_count": '
                    f'{poem_format["sentence_count"]},'
                ),
                (
                    '      "sentence_lengths": '
                    f'{json.dumps(poem_format["sentence_lengths"])},'
                ),
                (
                    '      "uniform_sentence_length": '
                    f'{json.dumps(poem_format["uniform_sentence_length"])}'
                ),
                "    }",
                f"  }}{',' if record_index < len(records) - 1 else ''}",
            ]
        )
    lines.append("]")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    normalize = build_normalizer()
    split_sequences = load_split_sequences(args.split_directory, normalize)
    repaired_records = 0
    inserted_sentences = 0
    changed_files = 0
    unconfirmed_records = 0
    partially_repaired_records = 0

    for qts_path in sorted(QTS_DIRECTORY.glob("*.json")):
        volume = int(qts_path.stem)
        ctext_path = args.ctext_directory / f"zh_{volume:04d}.json"
        zzu_path = args.zzu_directory / f"zhs_{volume:04d}.json"
        if not ctext_path.exists() or not zzu_path.exists():
            raise ValueError(f"Missing witnesses for QTS volume {volume}")

        qts_records = json.loads(qts_path.read_text(encoding="utf-8"))
        ctext_records = json.loads(ctext_path.read_text(encoding="utf-8"))
        zzu_records = json.loads(zzu_path.read_text(encoding="utf-8"))
        ctext_index = index_records(ctext_records, normalize)
        zzu_index = index_records(zzu_records, normalize)
        file_changed = False

        for record in qts_records:
            key = record_key(record, normalize)
            ctext_matches = ctext_index.get(key, [])
            if len(ctext_matches) != 1:
                continue

            complete_paragraphs = ctext_matches[0].get("content", [])
            current_sequence = normalized_sequence(
                record["paragraphs"], normalize
            )
            complete_sequence = normalized_sequence(
                complete_paragraphs, normalize
            )
            positions = subsequence_positions(
                current_sequence, complete_sequence
            )
            if (
                positions is None
                or len(complete_sequence) <= len(current_sequence)
            ):
                continue

            witness_sequences = [
                normalized_sequence(match.get("content", []), normalize)
                for match in zzu_index.get(key, [])
            ] + split_sequences.get(key, [])
            if any(
                witness == complete_sequence
                for witness in witness_sequences
            ):
                insert_positions = set(range(len(complete_sequence))) - set(
                    positions
                )
            else:
                insert_positions = corroborated_missing_positions(
                    positions,
                    complete_sequence,
                    witness_sequences,
                )
            if not insert_positions:
                unconfirmed_records += 1
                continue
            if len(insert_positions) < len(complete_sequence) - len(
                current_sequence
            ):
                partially_repaired_records += 1

            merged_paragraphs = merge_paragraphs(
                record["paragraphs"],
                complete_paragraphs,
                normalize,
                insert_positions,
            )
            if merged_paragraphs is None:
                raise ValueError(
                    f"Could not merge {qts_path.name}: "
                    f'{record["author"]}《{record["title"]}》'
                )

            inserted_sentences += len(insert_positions)
            repaired_records += 1
            record["paragraphs"] = merged_paragraphs
            record["format"] = calculate_poem_format(merged_paragraphs)
            file_changed = True

        if file_changed:
            changed_files += 1
            if args.write:
                qts_path.write_text(
                    serialize_records(qts_records),
                    encoding="utf-8",
                )

    action = "Repaired" if args.write else "Would repair"
    print(
        f"{action} {repaired_records} records in {changed_files} files; "
        f"inserted {inserted_sentences} sentence segments"
    )
    print(
        f"{partially_repaired_records} records received only the individually "
        "corroborated missing segments"
    )
    print(
        f"Left {unconfirmed_records} longer CText candidates unchanged "
        "because no missing segment had sufficient independent agreement"
    )


if __name__ == "__main__":
    main()
