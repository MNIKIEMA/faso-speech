# Plan

This plan turns the current design into implementation steps. Keep it updated
when priorities change or a phase is completed.

## Priorities

1. Moore Burkina content for Mooré, Dioula, and Fulfuldé.
2. Dash-based local speech data explorer for review, after candidate metadata
   exists and before adding new source families.
3. Bible sources with separate adapters for `jw.org` and `bible.com`, after the
   Moore Burkina pipeline and review loop are stable.
4. Webonary dictionary and lexical audio, out of scope for the first version.

The first usable dataset should come from Moore Burkina because the source
already exposes narrative and proverb audio with text, and many linked IPS pages
include timing metadata.

First-version target languages:

- Mooré
- Dioula
- Fulfuldé

French should be preserved when it appears as translation text or audio, but it
is supporting metadata unless a separate French translation dataset is planned.
Gulimancema/Goulma remains a language of interest because Bible coverage appears
available on `bible.com`, but it is not in the first implementation target set.

First-version processing focuses on paired audio+text records. Audio-only and
text-only records can be archived later, but they are not the current
dataset-building target.

## Phase 1: Stabilize The Moore Burkina Pipeline

Goal: replace the current Mooré contes prototype with a source-aware pipeline
that can archive and process Moore Burkina content across target languages and
content types.

Tasks:

- Add runtime dependencies: `msgspec`, Typer, `beautifulsoup4`, and `lxml`.
- Add the catalog, raw archive index, failure log, and processed metadata
  schemas described in `DESIGN.md`.
- Create data models for catalog entries, source records, parsed app-builder
  pages, archive records, statuses, timings, and text blocks.
- Create a manually maintained source catalog from the Moore Burkina seed pages
  in `DESIGN.md`.
- Represent each seed with language, content type, source URL, expected volume
  range, parser, priority, and notes.
- Split source-page discovery from app-builder parsing.
- Preserve source page provenance when discovering `media.ipsapps.org` app
  pages.
- Archive resolved app-builder `app.html`, audio URLs, downloaded audio, text
  blocks, timing metadata, language, content type, licensing fields, failure
  logs, and parser warnings.
- Require `app.html` for Moore Burkina app-builder records in every language.
- Treat Moore Burkina wrapper/source HTML as optional provenance. Save
  `source.html` once per catalog/source page when useful, not once per resolved
  app page.
- Move raw archives toward `data/raw_sources/<language>/<content_type>/...`.
- Make timed chunk extraction generic over language and content type.
- Keep candidate chunk metadata separate from reviewed or accepted chunks.
- Add validation statuses for missing audio, missing text, and suspicious
  timing metadata.
- Use Beautiful Soup with `lxml` for HTML parsing, keeping a small focused
  parser for JavaScript timing arrays such as `var timings = [...]`.

Definition of done:

- `faso-speech archive` can archive Moore Burkina seeds for at least Mooré
  contes.
- `faso-speech extract timed` can extract timed candidate chunks from archived
  data.
- Output metadata includes source URL, app URL, language, content type, audio
  URL, chunk path, text, timing, and status.
- The old hard-coded Mooré contes assumptions are either removed or isolated as
  compatibility wrappers.

## Phase 2: Expand Moore Burkina Coverage

Goal: use the generalized pipeline on the rest of the known Moore Burkina seed
catalog.

Tasks:

- Run the pipeline for Mooré contes, proverbes, and devinettes.
- Run the pipeline for Dioula contes, proverbes, and poemes.
- Run the pipeline for Fulfuldé contes and proverbes.
- Identify pages with site-provided timings versus pages that need VAD or
  manual segmentation.
- Record per-source coverage summaries: pages found, audio found, chunks
  produced, chunks needing review, and parser failures.
- Keep French translations archived, but do not mix them into local-language
  speech records without explicit metadata.

Definition of done:

- Each Moore Burkina language/content type has a raw archive index.
- Each processed candidate dataset has a metadata CSV.
- Known problematic timing cases are marked `needs_review` or
  `timing_mismatch`.

## Phase 3: Add Dash Review UI

Goal: create a local review interface as soon as Moore Burkina candidate chunk
metadata exists, before adding Bible sources. The UI should make extraction
quality visible so source parsing, timing cleanup, and metadata decisions are
guided by real review feedback.

Tasks:

- Build a Dash-based speech data explorer inspired by NVIDIA NeMo Speech Data
  Explorer.
- Read processed metadata CSVs or derived JSONL manifests.
- Show dataset statistics, sortable/filterable utterance tables, audio
  playback, waveform/spectrogram views, source metadata columns, status editing,
  and reviewer-note editing.
- Keep accepted/rejected/needs-review statuses round-trippable back into
  metadata files.
- Add optional later columns for vocabulary/OOV summaries, character-rate
  checks, audio peak/bandwidth estimates, and ASR prediction/error fields when
  `pred_text` exists.

Definition of done:

- A local Dash app can open a processed metadata file and review candidate
  chunks.
- Reviewer status and notes can be saved without corrupting existing metadata.
- The UI can filter by language, content type, source site, status, duration,
  and review note.
- Moore Burkina extraction issues discovered during review are captured as
  parser warnings, metadata statuses, or follow-up fixes before Bible source
  work begins.

## Phase 4: Add Bible Sources

Goal: add Bible/audio source support after the Moore Burkina pipeline is stable.
Model `jw.org` and `bible.com` as separate source adapters under the shared
`bible` content type because language coverage differs by site.

Tasks:

- Review the existing Bible scraper reference:
  `https://github.com/MNIKIEMA/MooreSpeechCorpora/blob/main/crawlers/bible/bible_scraper.py`.
- Review `https://github.com/sawallesalfo/jwsoup` as another candidate
  implementation reference for `jw.org`.
- Decide shared Bible metadata for chapters, readings, articles,
  translations/versions, books, chapters, verses, source publications, audio
  URLs, marker/timing availability, join status, and licensing notes.
- Implement a `jw.org` source adapter that emits the same raw archive model as
  Moore Burkina.
- Implement a separate `bible.com` source adapter. Do not reuse JW-specific
  language/media codes or marker assumptions.
- Preserve language, source URL, source site, Bible version/publication, audio
  URL, text, book/chapter/verse identifiers, marker metadata, and whether text,
  audio, and markers join cleanly.
- Use JW media codes `MM` for Mooré/Mossi and `JL` for Dioula/Jula in the first
  JW catalog entries.
- Probe Bible.com for Fulfuldé Burkina, where coverage appears available on
  `bible.com` but not on `jw.org`.
- Note Goulma/Gulimancema Bible.com availability, but keep Gulimancema out of
  first-version processing unless usable audio+text is confirmed and the
  language is explicitly brought back into scope.
- Add `extract untimed` behavior for chapter-level or paragraph-level audio/text
  records that do not have source timings.
- Run the JW adapter for Mooré/Mossi first, then Dioula/Jula after probing
  partial book coverage. Run Bible.com probing for Fulfuldé Burkina separately.

Definition of done:

- Bible records can be archived with the same index format as Moore Burkina
  while preserving site-specific fields.
- Mooré/Mossi JW records can be archived with audio, markers, and text.
- Dioula/Jula JW coverage is probed and archived where book/audio/text coverage
  exists.
- Fulfuldé Burkina Bible.com coverage is probed and documented.
- Gulimancema/Goulma Bible.com availability is documented but remains outside
  first-version processing.

## Later: Add Webonary

Goal: add dictionary and lexical audio only after connected-speech sources are
working. Webonary is out of scope for the first version.

Tasks:

- Treat Webonary as `dictionary` content type.
- Start with Mooré and Dioula Webonary sites.
- Extract entry URL, headword, part of speech, translations, example sentences,
  audio URL, and publication metadata.
- Store lexical audio separately from narrative speech.
- Decide later whether lexical clips should be used for ASR training,
  pronunciation modeling, evaluation, or vocabulary coverage only.

Definition of done:

- Webonary entries can be archived as lexical records.
- Audio-backed entries are clearly marked as lexical or example-sentence
  speech.
- Webonary data is not mixed into primary narrative training data unless the
  training recipe explicitly chooses it.

## Near-Term Next Steps

1. Add runtime dependencies: `msgspec`, Typer, `beautifulsoup4`, and `lxml`.
2. Add data models for catalog entries, source records, parsed app-builder
   pages, archive records, statuses, timings, and text blocks.
3. Move app-builder parsing into `src/faso_speech/parsers/app_builder.py` with
   tests using saved `app.html` fixtures.
4. Create the Python catalog structure for Moore Burkina seeds.
5. Build Moore Burkina discovery from catalog source pages to resolved
   app-builder content pages.
6. Build `faso-speech archive` from the catalog, requiring `app.html` and
   treating `source.html` as optional provenance.
7. Build `faso-speech extract timed` from the raw archive index.
8. Add failure logs, incremental skip behavior, and `faso-speech status`.
