# Shici Data

## Repository layout

- `raw/`: source-oriented normalized JSON, retained in corpus-specific files.
- `schema/`: the common poem record contract.
- `scripts/`: validation and deterministic release tooling.
- `manifest.json`: metadata for the current published data release.
- GitHub Releases: one compressed, application-ready JSON asset per corpus.

Raw and processed data intentionally live together in this repository. Raw
files preserve provenance and make corrections reviewable; release assets
provide a stable and efficient consumption interface.

## Build a release

```bash
python3 scripts/build_release.py --version v1.0.0
```

The command validates every poem, generates deterministic content-derived IDs,
and writes deterministic `jsonl.gz` assets to `dist/`. Exact duplicate records
receive occurrence suffixes such as `:2`. It also writes `manifest.json` with
poem counts, byte sizes, and SHA-256 checksums.

## Consumption

Applications should pin a release and download only the selected corpus:

```text
https://github.com/vippeterhou/shici-data/releases/download/v1.0.0/qts.jsonl.gz
```

Release assets contain one JSON poem object per line and conform to
`schema/poem.schema.json`. This allows consumers to decode large corpora
incrementally instead of holding both a full JSON object tree and normalized
application objects in memory. Consumers should verify the checksum from the
release manifest before parsing an asset.

## Updating data

### 1. Update the raw records

Edit, add, or remove records under `raw/`. Do not edit generated release
assets directly.

### 2. Build and validate a new version

Choose a version that has not been published before:

```bash
cd ~/Github/shici-data
VERSION=v1.1.0

python3 scripts/build_release.py --version "$VERSION"
python3 -m pytest -q
```

Review `manifest.json`, especially corpus counts, compressed sizes, and
checksums. The generated assets are written to `dist/` and intentionally
excluded from Git.

### 3. Commit and push the data changes

```bash
git status
git add raw manifest.json
git commit -m "Publish poetry data v1.1.0"
git push
```

Include changes under `scripts/`, `schema/`, or this README when the release
process or data contract also changed.

### 4. Publish the GitHub Release assets

```bash
gh release create "$VERSION" \
  dist/*.jsonl.gz \
  dist/manifest.json \
  --target main \
  --title "Shici Data $VERSION" \
  --notes "Updated and validated Chinese poetry datasets."
```

This creates the Git tag and release, then uploads all corpus assets and the
release manifest.

Verify the published assets:

```bash
gh release view "$VERSION" \
  --json url,assets \
  --jq '{url, assets: [.assets[].name]}'
```

The release URL follows this pattern:

```text
https://github.com/vippeterhou/shici-data/releases/tag/v1.1.0
```

### 5. Update consuming applications

For `vippeterhou/shici`, update `data_release.json` with the new version,
schema version, asset names, poem counts, and SHA-256 checksums. Run its tests,
then commit and push the application change. Streamlit Cloud redeploys when the
application repository changes.

Published release assets are immutable. Corrections require a new release
version so downstream applications remain reproducible.
