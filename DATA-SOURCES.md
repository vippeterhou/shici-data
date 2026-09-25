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

| Dataset/files | Original source | Project modifications |
|---|---|---|
| `qinhan`: `raw/qinhan/*.json` | `poetry-source`: `source/诗/秦/`, `source/诗/汉/` | Consolidated by dynasty; renamed fields; retained IDs; omitted ancillary fields; added tags and format metadata. |
| `qts`: `raw/qts/*.json` | `chinese-poetry`: `御定全唐詩/json/` | Added format metadata and editorial corrections; releases add missing IDs. |
| `quansongci`: `raw/quansongci/ci.song.*.json` | `chinese-poetry`: `宋词/` | Added format metadata; releases normalize titles and add missing IDs. |
| `quansongshi`: `raw/quansongshi/poet.song.*.json` | `chinese-poetry`: `全唐诗/` | Added format metadata; pruned unusable records; includes editorial corrections. |
| `sc300`: `raw/sc300/sc300.json` | `chinese-poetry`: `宋词/宋词三百首.json` | Renamed and relocated; added format metadata. |
| `shijing`: `raw/shijing/shijing.json` | `chinese-poetry`: `诗经/shijing.json` | Renamed fields; added author, IDs, tags, and format metadata. |
| `ts300`: `raw/ts300/ts300.json` | `chinese-poetry`: `全唐诗/唐诗三百首.json` | Renamed and relocated; added format metadata. |
| `weijinnanbeichao`: `raw/weijinnanbeichao/*.json` | `poetry-source`: `source/诗/三国/`, `source/诗/晋/`, `source/诗/南北朝/` | Consolidated by period; renamed fields; retained IDs; omitted ancillary fields; added tags and format metadata. |

Generated releases validate and compress records and keep each source's terms.
Update this file before adding a dataset.
