# Design

This document records the project design before more code is added. Update it
when the design changes, especially before changing the scraper or processing
pipeline.

## Goal

Build reproducible speech datasets for Burkina Faso languages, starting with
languages that have usable audio+text coverage:

- Mooré
- Dioula
- Fulfuldé

Gulimancema remains a language of interest, but it is out of scope for the first
implementation because no usable audio source has been identified yet.

The first source is Moore Burkina. Some Moore Burkina pages link to hosted IPS
app-builder pages on `media.ipsapps.org`; those IPS pages are linked app/media
pages from Moore Burkina, not an independent content source. Moore Burkina
contains multiple content types, including:

- contes
- proverbes
- devinettes

Known Mooré Moore Burkina seed pages:

- contes: start at
  `https://mooreburkina.com/fr/collection-2-12-contes-en-moor%C3%A9`;
  volumes 1 to 5.
- proverbes: start at
  `https://mooreburkina.com/fr/contes-et-proverbes-en-moor%C3%A9/proverbes-en-moor%C3%A9-vol-1`;
  volumes 1 to 12.
- devinettes:
  `https://mooreburkina.com/fr/contes-proverbes/devinettes-en-moor%C3%A9`.

Known Dioula Moore Burkina seed pages:

- contes: volume 1 appears to start at
  `https://mooreburkina.com/fr/dioula/5-contes-dioula`; volumes 2 to 4 start at
  `https://mooreburkina.com/fr/dioula/contes-en-dioula-avec-audio-volume-2`.
- proverbes:
  `https://mooreburkina.com/fr/dioula-fulfulde/contes-dioula-et-fran%C3%A7ais`.
- proverbes with volumes: volumes 1 to 4 start at
  `https://mooreburkina.com/fr/dioula/proverbes-lu-en-dioula-vol-1`.
- poemes:
  `https://mooreburkina.com/fr/dioula/po%C3%A8mes-en-dioula`.

Known Fulfuldé Moore Burkina seed pages:

- conte standalone:
  `https://mooreburkina.com/fr/fulfulde/15-contes-en-fulfulde`.
- proverbes: start at
  `https://mooreburkina.com/fr/fulfulde/proverbes-fulfulde-avec-audio`;
  volumes 2 to 4 start at
  `https://mooreburkina.com/fr/fulfulde/proverbes-fulfulde-avec-audio-vol2`.
- contes: volume 1 starts at
  `https://mooreburkina.com/fr/fulfulde/contes-lus-en-fulfulde`; volume 2 at
  `https://mooreburkina.com/fr/fulfulde/contes-lus-en-fulfulde-0`; volume 3 at
  `https://mooreburkina.com/fr/fulfulde/contes-lus-en-fulfulde-vol-3`;
  additional volumes/pages:
  `https://mooreburkina.com/fr/fulfulde/proverbes-dioula-vol-4`,
  `https://mooreburkina.com/fr/fulfulde/contes-lus-en-fulfulde-5`.

Most Moore Burkina pages appear to expose timestamped text through the linked
IPS app-builder pages. Those timings should be treated as the default first
alignment source for Moore Burkina content, while still preserving raw data and
validation status.

For Moore Burkina records in any language that use IPS app-builder pages, the
resolved IPS app-builder HTML is the required extraction artifact:

- the resolved IPS app-builder HTML page, which is the parsed page containing
  `var timings`, `T<label>` text blocks, the audio source URL, and next-page
  navigation.

The Moore Burkina source/wrapper HTML is useful for provenance and debugging,
but it is secondary. Archive it once per catalog/source page when convenient,
not once per resolved app page, and allow `source_html_path` to be empty when
the source URL and resolved `app_url` are enough to reproduce the record.

The root IPS app URL can be a small JavaScript redirect page such as
`https://media.ipsapps.org/mos/ora/co2/`. Store the resolved content page URL,
for example `https://media.ipsapps.org/mos/ora/co2/01-B001-001.html`, as the
record's `app_url`.

Additional source families are planned:

- Bible sources with separate adapters for `jw.org` and `bible.com`
- Webonary for Mooré, Fulfuldé, and Dioula lexical audio/text data in a later
  version

Webonary is out of scope for the first version. It should be revisited after
the Moore Burkina app-builder pipeline is stable, because it is mainly
dictionary or lexical audio rather than connected narrative speech.

Existing Bible scraping reference:

- `https://github.com/MNIKIEMA/MooreSpeechCorpora/blob/main/crawlers/bible/bible_scraper.py`
  can be reviewed before implementing Bible source adapters here.
- `https://github.com/sawallesalfo/jwsoup` is another candidate to review for
  the `jw.org` source adapter.

Fulfuldé remains a target language through Moore Burkina. Gulimancema should be
deferred until source discovery confirms usable audio+text coverage. Bible
coverage differs by site: Fulfuldé Burkina appears available on `bible.com` but
not on `jw.org`, so the pipeline must not treat Bible coverage as one uniform
source.

## Main Principle

Scraping and processing are separate phases.

Scraping should preserve raw source data with enough metadata to reproduce or
improve later processing. It should not make final alignment or quality
decisions.

Processing should read archived source data, extract candidate chunks, validate
them, and produce reviewed datasets.

## Data Dimensions

Do not treat language, content type, and source app as the same thing. They are
separate dimensions.

```text
language:     moore, dioula, fulfulde, gulimancema, french
content type: contes, proverbes, devinettes, ...
source site:  mooreburkina.com, jw.org, bible.com, webonary.org, ...
app/media:    media.ipsapps.org, ...
source app:   co1, co2, vol3, p1, ...
page:         01-B001-001, 01-001-003, ...
```

French appears mostly as translation text/audio. The local language for a page
must come from metadata, discovery, or configuration. It should not be hard-coded
inside a parser.

## Source Coverage

Different sources have different language and audio coverage. The pipeline
should support both audio-backed speech records and text-only records.

The first implementation focus is paired audio+text data. Audio-only records and
text-only records can be archived later for completeness, but they are not the
current processing target.

Current expected coverage:

```text
source            moore  dioula  fulfulde  gulimancema
Moore Burkina     yes    yes     yes       no
jw.org            yes    partial no        no
bible.com         probe  probe   yes       yes
Webonary audio    later  later   later     no
```

Because the first implementation focuses on paired audio+text records,
Gulimancema is not in the initial target set.

Current JW language notes:

- Mooré/Mossi: JW path `mos`, JW media code `MM`; Bible audio/text appears
  usable.
- Dioula/Jula: JW path `dyu`, JW media code `JL`; Bible coverage appears
  partial and should be probed by book.
- Fulfuldé/Fula: JW path `fuf`, JW media code `PLR`; do not include in the
  first JW scope until usable language-specific Bible audio/text is confirmed.
- Gulimancema: JW path `gux`, JW media code `GRC`; do not include in the first
  JW scope until usable Bible audio/text is confirmed.

Current Bible.com language notes:

- Fulfuldé Burkina: usable Bible coverage appears to be on `bible.com`, not
  `jw.org`. Treat this as a separate Bible source with its own source-site
  metadata, source IDs, page/API structure, licensing notes, and extraction
  rules.
- Goulma/Gulimancema: Bible coverage appears to be available on `bible.com`.
  Keep it out of the first implementation unless usable audio+text coverage is
  confirmed and the language is explicitly brought back into scope.
- Mooré and Dioula/Jula: probe before deciding whether `bible.com` should be
  included in the first Bible scope.

Source adapters should record whether audio is available instead of assuming
all discovered text can become speech chunks immediately.

## Current Issues

The current code started as a Mooré contes prototype. It works for that case,
but it should not become the final structure.

Known issues:

- `extract_timed_contes_chunks.py` assumes Mooré and contes.
- `BASE_URLS` are hard-coded to Mooré conte seed pages.
- Non-French text blocks are labeled as `moore`.
- Output paths include duplicated concepts such as `moore/contes_moore`.
- `discovery.py` returns only app URLs, losing the source page provenance.
- `raw_archive.py` accepts one global `--language` and `--content-type`, which
  can mislabel mixed sitemap results.
- HTML parsing is mostly regex-based and may be brittle.
- `app_builder.py` mixes HTTP, parsing, and file writing helpers.

## Proposed Package Layout

Keep the layout small while separating reusable components by responsibility.
If a component parses one page format, put it under `parsers/`. If it knows one
website, put it under `sources/`. If it works across sources, keep it as a
top-level module for now.

```text
src/faso_speech/
  http.py
  catalog.py
  archive.py
  audio.py
  processing.py
  validation.py
  cli.py

  sources/
    mooreburkina.py
    jw.py
    bible_com.py
    webonary.py

  parsers/
    app_builder.py
```

Possible responsibility split:

- `http.py`: URL quoting, fetching, downloading.
- `catalog.py`: manually maintained source seeds and source metadata.
- `sources/mooreburkina.py`: sitemap and source-page discovery.
- `sources/jw.py`: jw.org discovery and text/audio metadata extraction.
- `sources/bible_com.py`: Bible.com discovery and text/audio metadata
  extraction.
- `sources/webonary.py`: Webonary entry and audio discovery.
- `parsers/app_builder.py`: reusable parsing for app-builder HTML, including
  timestamps, text blocks, audio URL, title, and next-page URL.
- `archive.py`: write raw HTML, audio, text, timings, metadata, and index.
- `audio.py`: audio chunk cutting and shared ffmpeg behavior.
- `processing.py`: turn archived records into candidate chunks.
- `validation.py`: shared statuses and quality checks.
- `cli.py`: argument parsing and command orchestration only.

## Data Models

All structured data uses `msgspec.Struct` for validation and serialization.
Use `msgspec.json.encode`/`decode` for archive metadata files and
`msgspec.convert` for loading records from CSV rows.

Controlled-vocabulary fields use `Literal` types so invalid values fail at
decode time rather than propagating silently downstream:

```python
import msgspec
from typing import Literal

Language = Literal["moore", "dioula", "fulfulde", "gulimancema", "french"]
ContentType = Literal["contes", "proverbes", "devinettes", "poemes", "bible", "dictionary"]
SourceSite = Literal["mooreburkina.com", "jw.org", "bible.com", "webonary.org"]
Parser = Literal["app_builder", "jw", "bible_com", "webonary"]
```

Use `StrEnum` for the status vocabulary. It serializes cleanly to strings in
CSV exports and validates at assignment:

```python
from enum import StrEnum

class RecordStatus(StrEnum):
    ARCHIVED        = "archived"
    CANDIDATE       = "candidate"
    ACCEPTED        = "accepted"
    REJECTED        = "rejected"
    NEEDS_REVIEW    = "needs_review"
    NEEDS_ALIGNMENT = "needs_alignment"
    MISSING_AUDIO   = "missing_audio"
    MISSING_TEXT    = "missing_text"
    MISSING_TIMING  = "missing_timing"
    TIMING_MISMATCH = "timing_mismatch"
    PARSER_ERROR    = "parser_error"
    DOWNLOAD_ERROR  = "download_error"
```

Core structs:

```python
class SourceRecord(msgspec.Struct):
    source_url:    str
    source_site:   SourceSite
    language:      Language
    content_type:  ContentType
    app_url:       str = ""
    audio_url:     str = ""
    parser:        Parser = "app_builder"

class ParsedPage(msgspec.Struct):
    source_url:   str
    app_url:      str
    title:        str
    audio_url:    str
    text_blocks:  list[TextBlock]
    timings:      list[Timing]
    next_page:    str = ""
    warnings:     list[str] = []

class ArchiveRecord(msgspec.Struct):
    record_id:    str
    catalog_id:   str
    language:     Language
    content_type: ContentType
    source_site:  SourceSite
    source_url:   str
    app_url:      str
    parser:       Parser
    title:        str
    audio_url:    str
    audio_path:   str
    source_html_path: str = ""
    app_html_path:    str
    text_path:    str
    timings_path: str
    markers_path: str
    has_audio:    bool
    has_timing:   bool
    has_markers:  bool
    status:       RecordStatus
    warnings:     list[str]
    scraped_at:   str
    license:      str = "unknown"
    attribution:  str = "unknown"
```

Parsers define a common protocol so source adapters conform to the same
interface regardless of which site they target:

```python
from typing import Protocol

class PageParser(Protocol):
    def parse(self, html: str, record: SourceRecord) -> ParsedPage:
        ...
```

For app-builder records, the parser receives the resolved app-builder HTML, not
the Moore Burkina wrapper HTML. The source adapter is responsible for fetching
or reading the wrapper page, discovering the iframe/app URL, resolving redirects,
and passing the app HTML to the parser.

## Discovery Model

Discovery returns `SourceRecord` instances, not plain URLs. This preserves
provenance and allows later auditing without re-fetching source pages.

Not every source exposes an IPS-style app URL. `SourceRecord` is the canonical
model across all source adapters. Fields that do not apply to a given source
(such as `app_url` or `audio_url` for text-only pages) default to empty strings.

## Catalog Schema

Start with a Python catalog module. Each catalog entry should be explicit enough
that archiving does not need to infer core dataset labels from page text.

Required catalog fields:

- `id`: stable unique ID, for example `moore-contes-vol1`.
- `language`: canonical language code.
- `content_type`: canonical content type.
- `source_site`: source website, for example `mooreburkina.com` or `jw.org`.
- `source_url`: source page or seed URL.
- `parser`: parser name, for example `app_builder`, `jw`, or `webonary`.
- `priority`: rough implementation priority.
- `notes`: human-readable notes and caveats.

Optional catalog fields:

- `app_url`: direct app/media URL when known.
- `jw_language_code`: JW `langwritten` code when the source is `jw.org`.
- `bible_com_language`: Bible.com language or version identifier when the source
  is `bible.com`.
- `bible_version`: Bible translation/version identifier, especially for
  Bible.com where rights and audio availability can vary by version.
- `volume_start` and `volume_end`: expected volume range.
- `has_audio`: expected audio availability when known.
- `has_timing`: expected timing availability when known.
- `has_markers`: expected audio marker availability when known.
- `audio_format`: expected output format for derived chunks; defaults to
  `wav/mono/16kHz`.
- `include_french`: whether to archive French translation blocks from this
  entry; defaults to `true`.
- `license`: source license label or `unknown`.
- `attribution`: attribution text or `unknown`.

Audio format, French handling, and other processing decisions belong in the
catalog entry. They should not be overridden per run from the CLI.

## Configuration File

Network and runtime behavior is controlled by a `pyproject.toml` section or a
`faso_speech.toml` file, not by CLI flags. The CLI only overrides the two most
common toggles explicitly.

```toml
[faso_speech]
download_audio    = true
refresh           = false
timeout           = 30
retry             = 3
rate_limit_delay  = 1.0
```

CLI flags `--refresh` and `--no-audio` override the config for a single run.
All other network behavior uses config defaults.

## Raw Archive

The raw archive should preserve source facts, not final dataset decisions.

The index CSV is the pipeline's state file. It is append-only. Every archive run
reconciles against it before fetching. `status` and `scraped_at` columns are the
cache-invalidation mechanism. Rows are never overwritten; use `--refresh` to
delete rows and files explicitly before re-fetching.

Required raw fields:

- source page URL
- app page URL
- raw app/parser HTML when the parser reads a linked app/media page
- raw source HTML when a wrapper/source page is worth preserving
- audio URL
- downloaded audio path when available
- whether audio is available
- extracted text blocks
- site-provided timing metadata
- whether text and audio are both present
- language
- content type
- source site/app metadata
- parser warnings or errors

Preferred raw layout:

```text
data/raw_sources/
  moore/
    contes/
      vol5/
        source.html
        01-B021-001/
          app.html
          audio.mp3
          timings.csv
          text.csv
          metadata.json
  moore/
    proverbes/
      p1/
        source.html
        01-001-003/
          app.html
          audio.mp3
          timings.csv
          text.csv
          metadata.json
  index.csv
  failures.csv
```

For Moore Burkina app-builder records in any language, `app.html` is required
and is the resolved `media.ipsapps.org` content page that contains timings, text
blocks, audio URL, and next-page links. `source.html` is optional provenance for
the Moore Burkina wrapper page and should be stored once at the source/volume
level when saved. For sources without a separate wrapper/app split, use
`page.html` and leave `source_html_path` empty.

Records without both audio and text should not block archiving, but they are
outside the first processing focus. Mark them with statuses such as
`missing_audio`, `missing_text`, or `needs_review` instead of sending them to
the initial chunk extraction workflow.

Use stable IDs or URL hashes if there is any risk of path collision.

`metadata.json` files are written and read using `msgspec.json.encode`/`decode`
against `ArchiveRecord`. This means any metadata file that fails to decode
against the struct is caught immediately rather than propagating bad data.

Raw archive index columns:

- `record_id`
- `catalog_id`
- `language`
- `content_type`
- `source_site`
- `source_url`
- `app_url`
- `parser`
- `title`
- `audio_url`
- `audio_path`
- `source_html_path`
- `app_html_path`
- `text_path`
- `timings_path`
- `markers_path`
- `has_audio`
- `has_timing`
- `has_markers`
- `status`
- `warnings`
- `scraped_at`
- `license`
- `attribution`

Failure log columns:

- `timestamp`
- `phase`
- `record_id`
- `catalog_id`
- `url`
- `language`
- `content_type`
- `source_site`
- `error_type`
- `error_message`
- `retry_count`

The failure log path is always `<output-dir>/failures.csv`. It is not
configurable from the CLI.

## Processed Data

Processed data should be derived from raw archives.

Preferred processed layout:

```text
data/processed/
  moore/
    contes/
      timed_chunks/
      vad_chunks/
      reviewed_chunks/
      metadata.csv
    proverbes/
      timed_chunks/
      vad_chunks/
      reviewed_chunks/
      metadata.csv
    devinettes/
      timed_chunks/
      vad_chunks/
      reviewed_chunks/
      metadata.csv
```

Candidate chunks should be marked as candidates until reviewed or validated.

Processed chunk metadata columns:

- `chunk_id`
- `record_id`
- `catalog_id`
- `language`
- `content_type`
- `source_site`
- `source_url`
- `app_url`
- `source_audio`
- `audio_url`
- `label`
- `unit_type`
- `book`
- `chapter`
- `verse`
- `start`
- `end`
- `duration`
- `chunk_audio`
- `chunk_text`
- `text`
- `status`
- `review_note`
- `created_at`

## Bible Sources

Bible sources do not provide the same single-page paired timed text format as
Moore Burkina app-builder pages. Model `jw.org` and `bible.com` as separate
source sites under the shared `bible` content type. They may differ by language,
translation/version, audio availability, timing or marker metadata, page/API
shape, and licensing terms.

The shared Bible archive structure should preserve:

- source site, source URL, and fetched page/API response paths
- language and Bible version or publication identifier
- book, chapter, and verse identifiers
- text when fetched
- audio URL and downloaded audio when available
- source-provided markers or timing data when available
- join status between text, audio, and markers
- license, attribution, and usage notes

For `jw.org`, the media API can provide audio URLs and audio markers, such as
Bible verse start times and durations. Verse text can be fetched separately from
JW finder/pages and joined by language, book, chapter, and verse.

For `bible.com`, define a separate source adapter. Do not reuse JW-specific
language/media codes or marker assumptions. The adapter should discover the
Bible.com language/version/page structure, preserve version identifiers, and
record whether the source exposes usable audio, text, and timing/marker data.

The archive phase should preserve page/API responses, text when fetched, audio
URLs, downloaded audio, publication metadata, audio markers, language, source
URL, and licensing or attribution notes.

The first processing step for Bible sources should still be conservative:
archive the source response, page HTML, extracted verse text, audio metadata,
and marker metadata before cutting chunks. If markers and verse text join
cleanly, the records can become timed verse-level candidates. If text, markers,
or audio do not join cleanly, mark them as `needs_alignment` or `needs_review`.

The JW-specific archive schema should not be finalized until probe results from
`scripts/fetch_jw_probe.py` are in hand. The probe fetches JW media metadata for
one target language and, with `--fetch-text`, sampled JW finder pages with verse
text. Use it to inspect audio URLs, publication fields, marker fields, and text
fields before committing to a schema.

Add a separate Bible.com probe before finalizing Bible.com schema details,
especially for Fulfuldé Burkina coverage.

## Timed Chunk Extraction

The timed extractor should be generic over language and content type. It should
not be named only for contes.

For Moore Burkina content, timestamped text is expected to be common. The
processing pipeline should first try site-provided timings, then use VAD or
manual review when timings are missing, incomplete, or suspicious.

Language inference should use the source language from the catalog as the
default. Source markup such as `bdit` is only a weak signal because some Moore
Burkina pages use it for local-language text as well as French translations.
The archive parser may store a best-effort language label, but processing
should re-check each text block and record any correction in review metadata
rather than silently trusting stale raw labels.

If the lightweight rules are not sufficient, add a GlotLID-based validation
step in processing. GlotLID should be a fallback for uncertain or conflicting
cases, not a mandatory dependency for every archive run. The raw archive should
remain reproducible without model downloads; model-based language ID belongs in
derived processing outputs and should record the model name/version, score, and
decision reason.

```python
def infer_language(fragment, text, source_language):
    if source_markup_suggests_translation(fragment) and looks_french(text):
        return "french"
    return source_language
```

## CLI

The CLI is thin. It controls what to run, what data scope to use, and where
files go. All source discovery, parsing, archiving, validation, and audio
processing live outside CLI functions. Use Typer for implementation.

### Design Principles

**Scope is controlled by catalog ID or a filter expression**, not by independent
`--language`, `--content-type`, and `--source-site` flags on every subcommand.
For real pipeline runs, you are almost always targeting a specific catalog entry
or a known language+content-type pair. The cross-product of four independent
flags creates combinations that are never used in practice.

**Network and runtime behavior comes from the config file**, not from flags. The
CLI only exposes `--refresh` and `--no-audio` as explicit overrides for the two
most common single-run toggles. Timeout, retry, and rate limiting use config
defaults.

**Processing decisions belong in the catalog entry**, not the CLI. Audio format,
sample rate, channels, padding, and French inclusion are per-catalog-entry
fields. They are not overridden per run.

**Output paths follow a convention relative to `--output-dir`**. The failure log
is always `<output-dir>/failures.csv`. It is not a separate flag.

### Subcommands

```text
faso-speech catalog list
faso-speech discover
faso-speech archive
faso-speech extract timed
faso-speech extract untimed
faso-speech status
```

### Command Reference

```bash
# List catalog entries, optionally filtered
faso-speech catalog list [--filter EXPR]

# Discover linked records from catalog seed pages
faso-speech discover \
  [--catalog-id ID | --filter EXPR] \
  --output-dir DIR \
  [--dry-run]

# Archive raw source/app HTML, metadata, timings, text, and audio
faso-speech archive \
  [--catalog-id ID | --filter EXPR] \
  --output-dir DIR \
  [--refresh] \
  [--no-audio] \
  [--dry-run]

# Extract candidate chunks from archived timing metadata
faso-speech extract timed \
  --input-index PATH \
  [--catalog-id ID | --filter EXPR] \
  --output-dir DIR \
  [--dry-run]

# Prepare untimed records for VAD or forced alignment
faso-speech extract untimed \
  --input-index PATH \
  [--catalog-id ID | --filter EXPR] \
  --output-dir DIR \
  [--dry-run]

# Summarize archive coverage and status per catalog entry
faso-speech status \
  --input-index PATH
```

### Filter Expression

`--filter` accepts a space-separated list of `key=value` pairs. Valid keys are
`language`, `content_type`, `source_site`, and `priority`. Values must match
the controlled vocabulary defined in the data models.

```bash
--filter "language=moore content_type=contes"
--filter "source_site=jw.org"
--filter "priority=1"
```

`--catalog-id` and `--filter` are mutually exclusive. When neither is provided,
all catalog entries are in scope.

### Flags Intentionally Omitted

These flags are omitted from the first CLI version and should only be added if
a real need emerges:

- `--max-pages`, `--max-entries`: traversal limits belong in catalog entry notes
  and config, not as per-run overrides.
- `--verbose` / `--quiet`: use Python logging level via the environment
  (`LOG_LEVEL=DEBUG`) rather than CLI flags.
- `--failure-log`: always `<output-dir>/failures.csv`.
- `--seed-url`: use a local catalog entry for experiments instead.
- `--timeout`, `--retry`, `--rate-limit-delay`: always from config.

### `faso-speech status`

Replaces what a DVC pipeline graph would show. Reads the index CSV and prints
per-catalog-entry counts for: pages archived, audio found, timings found, chunks
created, failures, and current status distribution. This is the primary way to
know what has been done and what remains.

## Quality And Validation

Site-provided timings are useful but not final truth. Some pages can expose
timing metadata that points into a longer shared audio file or has misleading
alignment.

Processing should support statuses defined in `RecordStatus`. Validation can
include:

- VAD checks
- duration thresholds
- missing text/audio checks
- manual review

## Dependencies

Runtime Python dependencies:

- `msgspec` for struct validation, JSON serialization, and CSV row conversion.
- Typer for the public CLI.
- Beautiful Soup with the `lxml` parser for forgiving HTML parsing. Use it for
  wrapper-page iframe discovery, titles, links, text blocks, audio sources, and
  next-page links. Keep a small focused parser for JavaScript timing arrays such
  as `var timings = [...]`.
- `beautifulsoup4` and `lxml` as runtime dependencies.

External tools:

- `ffmpeg` for audio conversion and chunk cutting.

Development dependencies:

- `ruff` for linting and formatting.
- Test tooling should be added before parser and archive behavior is refactored.

## Testing Strategy

Start with focused tests around reusable components:

- Catalog filtering tests for language, content type, source site, and catalog
  ID.
- Parser tests using saved `app.html` fixtures for app-builder pages.
- Archive tests that write to a temporary directory and verify `app.html`,
  `metadata.json`, `text.csv`, `timings.csv`, `index.csv`, and `failures.csv`
  for Moore Burkina app-builder records; verify `source.html` only when the
  wrapper page is intentionally archived. For single-layer sources, verify
  `page.html` instead.
- Processing tests that read small archived fixtures and verify candidate chunk
  metadata without requiring network access.
- Validation tests for status assignment such as `missing_audio`,
  `missing_text`, `missing_timing`, `needs_review`, and `needs_alignment`.
- CLI tests with Typer's test runner for argument parsing, dry runs, and summary
  output.
- msgspec decode tests that verify invalid `language`, `content_type`, or
  `status` values raise `ValidationError` at decode time.

Network tests should be opt-in. Default tests should use local fixtures so they
are reproducible and fast.

## Current Code Migration

Migrate gradually from the current prototype:

- `scraping/app_builder.py`: split into `http.py`, `parsers/app_builder.py`,
  and `archive.py`.
- `scraping/discovery.py`: move Moore Burkina discovery into
  `sources/mooreburkina.py`.
- `scraping/raw_archive.py`: move orchestration into Typer CLI commands and raw
  writing into `archive.py`.
- `processing/extract_timed_contes_chunks.py`: move timing-based processing into
  `processing.py` and audio cutting into `audio.py`.
- `processing/align_contes_segments.py`: keep the alternating speech/text logic
  available for future VAD or manual alignment workflows.

## Additional Design Considerations

- Licensing and attribution: track source license text or notes, copyright
  owner, attribution requirements, source URL, scrape date, and any known usage
  constraints before publishing or training on the data.
- Speaker, dialect, and orthography metadata: preserve narrator, region,
  organization, dialect, script, or orthography variant when available. Even
  partial labels can help with evaluation and avoid accidental leakage.
- Deduplication: track URL hashes, audio hashes, text hashes, and
  near-duplicate text candidates before final dataset release. The same story,
  proverb, or audio file may appear through multiple pages or volumes.
- Train/dev/test split policy: do not split at chunk level only. Prefer
  splitting by source page, story/proverb, speaker, or source audio file so
  adjacent chunks from the same recording do not leak across splits.
- Long shared audio files: keep the shared audio URL and mark records for timing
  review when page timings point into a compilation audio file or the offset is
  uncertain.
- French translations: archive French with local-language records, but keep
  local speech, French speech, and text translation pairs distinguishable in
  metadata. A later release can decide whether to build a parallel translation
  dataset.
- Text normalization: preserve raw text, then store normalized text separately
  for punctuation, casing, Unicode normalization, apostrophes, numerals, and
  spacing decisions.
- Audio processing: preserve downloaded source audio and write derived chunks
  separately. Derived chunks can normalize sample rate, channels, duration,
  padding, and loudness, while the raw archive remains reproducible.
- Manual review workflow: make candidate chunks reviewable through metadata
  CSVs or a small review tool, with accepted/rejected status, reviewer notes,
  and reasons such as bad alignment, bad text, silence, or wrong language.
- Local review UI: when CSV review becomes too slow, build a Dash-based local
  speech data explorer inspired by NVIDIA NeMo Speech Data Explorer. It should
  read the processed metadata CSV or a derived JSONL manifest and provide dataset
  statistics, sortable/filterable utterance tables, audio playback,
  waveform/spectrogram views, source metadata columns, status editing, and
  reviewer-note editing. Optional later features can include vocabulary/OOV
  summaries, character-rate checks, audio peak/bandwidth estimates, and ASR
  prediction/error columns when `pred_text` is available.
- Incremental and resumable runs: the index CSV is append-only; skip existing
  records by default and use `--refresh` to re-fetch explicitly. Avoid
  duplicating index rows. Log failures to `failures.csv`.
- Coverage and status: use `faso-speech status` to summarize pages inspected,
  pages archived, audio found, timings found, chunks created, failures, and
  review status by source, language, and content type.
- Polite and reproducible crawling: use a clear user agent, timeouts,
  retry/backoff, rate limiting, failure logs, and source scrape timestamps.
  Check source terms and robots guidance before broad crawling.

## Before Implementation

Answer these before changing the scraper or processing pipeline:

- Initial target language codes: use `moore`, `dioula`, `fulfulde`, and
  `french`. Keep `gulimancema` in the controlled vocabulary for future
  text-only or newly discovered audio+text sources, but do not target it in the
  first implementation.
- Content types: use `contes`, `proverbes`, `devinettes`, `poemes`, `bible`,
  and `dictionary`.
- Raw data root: use `data/raw_sources`.
- Processed data root: use `data/processed`.
- Source catalog: start with a Python catalog module, then move to TOML or YAML
  later only if editing seeds in Python becomes awkward.
- Discovery strategy: use the manually maintained catalog first. Sitemap
  discovery can remain an optional helper.
- First processing scope: focus on records where both audio and text are
  present. Audio-only and text-only records may be archived, but they are not
  the current dataset-building target.
- Metadata schema: every archived record should store source URL, app/media URL
  when present, language, content type, source site, parser, title, audio URL,
  audio path, raw app/parser HTML path, optional raw source HTML path, text path,
  timings path, scrape timestamp, warning messages, and status. All metadata
  files are written as JSON using
  `msgspec.json.encode` against `ArchiveRecord`.
- French handling: archive French translation text or audio when present, label
  it as `french`, and keep it distinguishable from local-language speech.
  Whether French blocks are archived for a given catalog entry is controlled by
  the `include_french` catalog field.
- Licensing fields: store license, copyright owner, attribution, usage notes,
  and license URL fields now, even when the value is `unknown`.
- Audio chunks: write derived chunks as WAV, mono, 16 kHz by default. Override
  per catalog entry if needed.
- Review workflow: start with status and review-note columns in metadata CSVs.
- Failure logs: write failed URL, source record ID, phase, exception message,
  retry count, and timestamp to `<output-dir>/failures.csv` during discovery,
  archiving, and processing.
- Incremental runs: skip existing downloaded audio and archived pages by
  default, avoid duplicate index rows, and require an explicit `--refresh` flag
  to re-fetch existing records.

## Open Questions

Remaining questions to answer before the relevant phase:

1. For Bible sources, what metadata should distinguish Bible chapters, readings,
   articles, translations/versions, and other audio material under the `bible`
   content type? Defer finalizing JW and Bible.com archive schemas until source
   probe results are in hand.
2. When Gulimancema work resumes, should text-only sources be stored in the same
   raw archive even when no audio is available?
