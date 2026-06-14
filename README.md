# faso-speech

Tools for collecting and preparing speech data from Burkina Faso language
resources.

Initial focus:

- Mooré
- Dioula
- Fulfuldé

Gulimancema/Goulma remains a language of interest, especially for future Bible
source work, but it is not in the first implementation target set. The first
processing target is paired audio+text data.

The project separates scraping from processing:

1. Save raw source data from websites.
2. Process, validate, chunk, and filter the data later.

This makes the corpus reproducible. If alignment logic improves, the raw data
can be processed again without scraping the source websites again.

## Sources

The first source family is Moore Burkina. Moore Burkina pages often embed or
link IPS app-builder pages hosted on `media.ipsapps.org`. For those records,
the resolved app-builder page is the required extraction artifact:

```text
app.html
```

That page contains the timing array, text blocks, audio URL, and next-page
links. The Moore Burkina wrapper page can be saved as optional provenance, but
it is not required for chunk extraction.

Bible sources are planned after the Moore Burkina pipeline is stable. `jw.org`
and `bible.com` are modeled as separate source adapters under the shared
`bible` content type because language and audio coverage differ by site.
Webonary lexical audio is out of scope for the first version.

## Raw Data

The raw scraper should preserve:

- source page URL
- app page URL
- resolved app-builder HTML as `app.html`
- optional source/wrapper HTML as `source.html`
- audio URL
- downloaded audio
- extracted text blocks
- site-provided timing metadata
- language
- content type
- metadata

Example layout:

```text
data/raw_sources/
  moore/
    contes/
      co2/
        source.html
        01-B021-001/
          app.html
          audio.mp3
          timings.csv
          text.csv
          metadata.json
  index.csv
  failures.csv
```

## Processing

Processing should happen after scraping:

- use site timings when available
- validate chunks with VAD
- fall back to VAD when timings are missing
- mark suspicious examples for review

Example layout:

```text
data/processed/
  moore/
    contes/
      timed_chunks/
      vad_chunks/
      reviewed_chunks/
      metadata.csv
```

## Development

Create the environment with uv:

```bash
uv sync
```

Run commands inside the project environment:

```bash
uv run python --version
```

List known catalog entries:

```bash
uv run faso-speech catalog list
uv run faso-speech catalog list --filter "language=moore content_type=contes"
```

Archive one Moore Burkina app-builder page without downloading audio:

```bash
uv run faso-speech archive \
  --catalog-id moore-contes-vol2 \
  --output-dir data/raw_sources \
  --no-audio \
  --max-pages 1
```

Archive and download audio:

```bash
uv run faso-speech archive \
  --catalog-id moore-contes-vol2 \
  --output-dir data/raw_sources \
  --max-pages 1
```

Summarize archived records:

```bash
uv run faso-speech status --input-index data/raw_sources/index.csv
```

Extract timed candidate chunks from the raw archive:

```bash
uv run faso-speech extract timed \
  --input-index data/raw_sources/index.csv \
  --output-dir data/processed
```

Review extracted candidate chunks in the local Dash UI:

```bash
uv run faso-speech review data/processed/metadata.csv
```

The older prototype commands are still present for compatibility:

```bash
uv run faso-extract-timed-contes --max-pages-per-volume 1
uv run faso-scrape-raw --use-default-seeds --max-pages-per-seed 1
```

Run the VAD/segment CSV fallback aligner:

```bash
uv run faso-align-contes-segments \
  --segments path/to/file.segments.csv \
  --text path/to/file.txt
```

Run segmentation for a processed tree:

```bash
uv run faso-speech preprocess segments \
  --input-dir data/processed \
  --language moore
```

This reads `data/processed/metadata.csv`, segments each unique `chunk_audio`,
and writes reusable segment CSVs under
`data/processed/<language>/<content_type>/segments/`. Use `--language` and
`--content-type` to scope a run, and `--dry-run` to preview the jobs first.

Current processed audio totals from `data/processed/metadata.csv`:

| Language | Rows | Duration | < 0.72s rows |
| --- | ---: | ---: | ---: |
| moore | 5,746 | 05:41:41.870 | 88 |
| fulfulde | 2,260 | 02:41:47.140 | 103 |
| dioula | 1,073 | 00:49:45.910 | 26 |
| french | 212 | 00:12:23.400 | 4 |

Prepare segmented training audio for Hugging Face upload:

```bash
uv run faso-speech preprocess hf-training \
  --audio path/to/source.mp3 \
  --text path/to/transcript.txt \
  --output-dir data/hf/moore-contes \
  --language moore
```

If `--segments` is omitted, the command runs `inaSpeechSegmenter` and writes the
generated segment CSV next to `metadata.csv`. The output folder contains
`chunks/` audio plus a Hugging Face-friendly `metadata.csv` with `file_name`,
`text`, `language`, `duration`, and `char_per_second`. Transcript lines that
start with a digit have that leading digit removed before export.

To build an embedded Hugging Face `Audio(decode=False)` dataset without
TorchCodec, use the optional Arrow export helper. It can read either an export
folder with `file_name` metadata or `data/processed` with `chunk_audio`
metadata:

```bash
uv run scripts/export_hf_audio_arrow.py data/processed \
  --language moore \
  --output-parquet data/hf/moore/parquet
```

The helper reads `file_name` or `chunk_audio` paths from `metadata.csv`, stores
each audio as `{"bytes": ..., "path": ...}`, and writes a deterministic 90%
`train` / 10% `validation` split by default. It can also push directly with
`--repo-id`.

The default export is intentionally small for ASR training:

| Column | Purpose |
| --- | --- |
| `audio` | Embedded `Audio(decode=False)` value with `bytes` and `path` |
| `text` | Transcript |
| `language` | Language label |
| `duration` | Chunk duration from metadata |
| `chunk_id` | Stable chunk identifier |
| `record_id` | Source record identifier |
| `content_type` | Source content type |

To add specific metadata columns, repeat `--column`:

```bash
uv run scripts/export_hf_audio_arrow.py data/processed \
  --language moore \
  --column text \
  --column language \
  --column duration \
  --column source_url
```

For a provenance/debug export with every metadata column, use:

```bash
uv run scripts/export_hf_audio_arrow.py data/processed \
  --language moore \
  --include-all-metadata
```

Use one Hugging Face config per dataset:

```bash
uv run scripts/export_hf_audio_arrow.py data/processed \
  --repo-id madoss/faso-speech \
  --config-name moore \
  --language moore

uv run scripts/export_hf_audio_arrow.py data/processed \
  --repo-id madoss/faso-speech \
  --config-name dioula \
  --language dioula

uv run scripts/export_hf_audio_arrow.py data/processed \
  --repo-id madoss/faso-speech \
  --config-name fulfulde \
  --language fulfulde
```

Add dependencies with:

```bash
uv add package-name
```

Add development dependencies with:

```bash
uv add --dev package-name
```

Run checks:

```bash
just lint
just pre-commit
```
