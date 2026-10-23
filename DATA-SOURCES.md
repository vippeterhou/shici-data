# Data Sources

The root [MIT License](LICENSE) covers this project's original code and
project-created data contributions. Third-party data keeps its source terms.

## Sources

| Source | Author/copyright | License |
|---|---|---|
| [`chinese-poetry/chinese-poetry`](https://github.com/chinese-poetry/chinese-poetry) | Copyright (c) 2016 JackeyGao | MIT [notice](LICENSES/chinese-poetry-MIT.txt); underlying data terms are not separately stated. |
| [`snowtraces/poetry-source`](https://github.com/snowtraces/poetry-source) | Copyright (c) 2020 snowtraces | MIT [notice](LICENSES/poetry-source-MIT.txt) for code/configuration; dataset terms are not separately stated. |
| [Wikisource `唐詩三百首`](https://zh.wikisource.org/wiki/唐詩三百首) | Original poems by their named Tang-dynasty authors; anthology collected by Sun Zhu and Xu Lanying in 1763 | Public domain; the source pages mark the works with `PD-old`. |
| [Wikisource `宋詞三百首`](https://zh.wikisource.org/wiki/宋詞三百首) | Original ci by their named authors; anthology compiled by Zhu Xiaozang and published in 1924 | Public domain; the source page marks the anthology with `Pd` using the compiler's 1931 death year and 1924 publication year. |

Dataset rows inherit their source's attribution and license status; no separate
dataset copyright holders are identified upstream.

## Datasets

Raw records retain only normalized core poem fields. Release IDs are generated
from content. Shijing also retains its chapter and section hierarchy.

| Dataset/files | Original source | Project modifications |
|---|---|---|
| `qinhan`: `raw/qinhan/*.json` | `poetry-source`: `source/诗/秦/`, `source/诗/汉/` | Consolidated by dynasty; renamed fields; omitted ancillary fields; split bundled works; pruned prose and irrecoverably incomplete records; added format metadata and editorial corrections. |
| `qts`: `raw/qts/*.json` | `chinese-poetry`: `御定全唐詩/json/001.json`–`900.json` | Split bundled poem suites into individually numbered records; removed exact duplicates and imported header/footer artifacts; normalized titles, numbering, and metadata; repaired recoverable glyph placeholders; restored omitted text while retaining surviving edition-specific readings; and added format metadata. Omission repairs require exact sentence-level corroboration from at least two aligned witnesses among `poetry-source`'s `全唐诗/CText_JSON_cht/` and `全唐诗/ZZU_JSON_chs/` and `chinese-poetry`'s split `全唐诗/poet.tang.*.json`. Wikisource or primary-edition scans are used for ambiguous passages. |
| `qsc`: `raw/qsc/*.json` | `chinese-poetry`: `宋词/`, pinned to commit [`b8594f8`](https://github.com/chinese-poetry/chinese-poetry/commit/b8594f81a89752241442f2ce267d6f66f96704ee) in `source-locks/qsc.json` | Renamed source batches to zero-padded numeric offsets; removed the redundant 2019 supplement; consolidated each linked `九张机` suite into one record; renamed `rhythmic` to `title`; added QSC-specific format metadata; repaired recoverable encoding corruption, lacunae, and author names from documented witnesses; removed exact duplicates, damaged duplicate variants, and records containing no recoverable text; normalized upstream numeric author disambiguators; retains the canonical copies of high-confidence ci-form works removed from QSS; and removed two regular-form poems retained in QSS. Editorial changes are recorded in `editorial/qsc-cleanup.json` and verified by `python3 -m scripts.audit_qsc`. |
| `qss`: `raw/qss/*.json` | `chinese-poetry`: `全唐诗/poet.song.*.json` | Renamed source batches to zero-padded numeric offsets; added format metadata; pruned unusable records; includes editorial corrections; removed 94 high-confidence ci-form duplicates retained in QSC and retains two regular-form poems removed from QSC. Every reclassification is recorded in `editorial/song-genre-reclassifications.json` and verified by `python3 -m scripts.audit_song_reclassifications`. |
| `sc300`: `raw/sc300/sc300.json` | Wikisource: [`宋詞三百首`](https://zh.wikisource.org/wiki/宋詞三百首), pinned to [revision 2649131](https://zh.wikisource.org/w/index.php?title=宋詞三百首&oldid=2649131) in `source-locks/sc300.json` | Rebuilt as the canonical 283-entry anthology from the pinned revision's displayed primary readings; rendered in Simplified Chinese (`zh-hans`); excluded prefaces, annotations, and alternate readings; normalized tune titles and modern mainstream attributions; represented displayed lines as paragraph arrays; added format metadata. Source overrides and evidence are recorded in `editorial/sc300-attributions.md`. The reproducible audit is `python3 -m scripts.audit_sc300`. |
| `shijing`: `raw/shijing/shijing.json` | `chinese-poetry`: `诗经/shijing.json` | Renamed fields; added author and format metadata; retained chapter and section hierarchy. |
| `ts300`: `raw/ts300/ts300.json` | Wikisource: [`唐詩三百首`](https://zh.wikisource.org/wiki/唐詩三百首) | Rebuilt as the canonical 320-entry anthology from Wikisource's displayed primary readings; rendered in Traditional Chinese (`zh-hant`); excluded prefaces, annotations, and alternate readings; normalized titles and attributions; represented displayed lines as paragraph arrays; added format metadata. |
| `wjnbc`: `raw/wjnbc/*.json` | `poetry-source`: `source/诗/三国/`, `source/诗/晋/`, `source/诗/南北朝/` | Consolidated into Three Kingdoms, Jin, and Northern and Southern Dynasties shards; renamed fields; omitted ancillary fields; added format metadata; split labeled collections into individual poems; normalized titles; removed duplicate records and poems with unrecoverable lacunae; corrected the order, numbering, and duplicate entries in Ruan Ji's 82 `咏怀` poems; resolved one disputed attribution using the source anthology's editorial note. |

Generated releases validate and compress records and keep each source's terms.
Update this file before adding a dataset.

Earlier project revisions seeded `ts300` and `sc300` from
`chinese-poetry`. The current files were independently rebuilt from
Wikisource and no longer use `chinese-poetry` as a source.
