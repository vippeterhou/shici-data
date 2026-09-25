# Data Sources

The root [MIT License](LICENSE) covers this project's original code and
project-created data contributions. Third-party data keeps its source terms.

## Sources

| Source | Author/copyright | License |
|---|---|---|
| [`chinese-poetry/chinese-poetry`](https://github.com/chinese-poetry/chinese-poetry) | Copyright (c) 2016 JackeyGao | MIT [notice](LICENSES/chinese-poetry-MIT.txt); underlying data terms are not separately stated. |
| [`snowtraces/poetry-source`](https://github.com/snowtraces/poetry-source) | Copyright (c) 2020 snowtraces | MIT [notice](LICENSES/poetry-source-MIT.txt) for code/configuration; dataset terms are not separately stated. |

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
| `sc300`: `raw/sc300/sc300.json` | `chinese-poetry`: `宋词/宋词三百首.json` | Renamed and relocated; added format metadata. |
| `shijing`: `raw/shijing/shijing.json` | `chinese-poetry`: `诗经/shijing.json` | Renamed fields; added author and format metadata; retained chapter and section hierarchy. |
| `ts300`: `raw/ts300/ts300.json` | `chinese-poetry`: `全唐诗/唐诗三百首.json` | Renamed and relocated; added format metadata. |
| `weijinnanbeichao`: `raw/weijinnanbeichao/*.json` | `poetry-source`: `source/诗/三国/`, `source/诗/晋/`, `source/诗/南北朝/` | Consolidated by period; renamed fields; omitted ancillary fields; added format metadata; split labeled collections into individual poems; normalized titles; removed duplicate records and poems with unrecoverable lacunae; corrected the order, numbering, and duplicate entries in Ruan Ji's 82 `咏怀` poems; resolved one disputed attribution using the source anthology's editorial note. |

Generated releases validate and compress records and keep each source's terms.
Update this file before adding a dataset.
