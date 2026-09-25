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
| `qts`: `raw/qts/*.json` | `chinese-poetry`: `御定全唐詩/json/` | Added format metadata and editorial corrections. |
| `quansongci`: `raw/quansongci/ci.song.*.json` | `chinese-poetry`: `宋词/` | Renamed `rhythmic` to `title`; added format metadata. |
| `quansongshi`: `raw/quansongshi/poet.song.*.json` | `chinese-poetry`: `全唐诗/` | Added format metadata; pruned unusable records; includes editorial corrections. |
| `sc300`: `raw/sc300/sc300.json` | `chinese-poetry`: `宋词/宋词三百首.json`; Wikisource: [`宋詞三百首`](https://zh.wikisource.org/wiki/宋詞三百首) | Renamed and relocated; rebuilt in the canonical 283-entry anthology order; removed seven non-index or substitute records retained in `quansongci`; restored ten missing ci from Wikisource; normalized tune titles and attributions; applied source-backed textual corrections; added format metadata. |
| `shijing`: `raw/shijing/shijing.json` | `chinese-poetry`: `诗经/shijing.json` | Renamed fields; added author and format metadata; retained chapter and section hierarchy. |
| `ts300`: `raw/ts300/ts300.json` | `chinese-poetry`: `全唐诗/唐诗三百首.json`; Wikisource: [`題破山寺後禪院`](https://zh.wikisource.org/wiki/題破山寺後禪院), [`送李中丞歸漢陽別業`](https://zh.wikisource.org/wiki/送李中丞歸漢陽別業), and [`寄揚州韓綽判官`](https://zh.wikisource.org/wiki/寄揚州韓綽判官) | Renamed and relocated; rebuilt in the canonical 320-entry anthology order; removed non-index and duplicate records; restored three missing poems from Wikisource; normalized titles and attributions; removed square-bracket editorial notation; added format metadata. |
| `weijinnanbeichao`: `raw/weijinnanbeichao/*.json` | `poetry-source`: `source/诗/三国/`, `source/诗/晋/`, `source/诗/南北朝/` | Consolidated by period; renamed fields; omitted ancillary fields; added format metadata; split labeled collections into individual poems; normalized titles; removed duplicate records and poems with unrecoverable lacunae; corrected the order, numbering, and duplicate entries in Ruan Ji's 82 `咏怀` poems; resolved one disputed attribution using the source anthology's editorial note. |

Generated releases validate and compress records and keep each source's terms.
Update this file before adding a dataset.
