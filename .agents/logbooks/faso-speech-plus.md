# Faso Speech Plus (`scripts/build_faso_speech_plus.py`)

Concatenates `madoss/faso-speech` with external HF ASR datasets into three
configs (`moore`, `bambara_jula`, `fula`). `MANIFEST` is the authoritative list
of sources, column mappings, licenses and per-source notes.

## 2026-10-02

- Tagged the Hub repo `v0.1.0` at `a8ee7fba` before schema changes.
- Added `speaker_id` and `gender` to `COMMON_FEATURES`, with per-source
  `speaker_column`/`gender_column` in the manifest. Speaker IDs are stored as
  `<source entry id>:<upstream id>` because upstream IDs (`spk01`,
  `SPEAKER_00`) collide across sources. Gender is normalized `M`/`F` ->
  `male`/`female`, otherwise null.
- Mapped: faso-speech (speaker + gender, once it is re-exported with those
  columns), Omnilingual (speaker), WaxalNLP (speaker; gender is empty),
  Koumankan4Dyula (gender only). Dyula Bible deliberately not mapped; see
  [`speakers.md`](speakers.md).
- Next release: re-export faso-speech first, then rebuild this, push, tag
  `v0.2.0`.
- Card license set to CC-BY-4.0 (maintainer decision); faso-speech manifest
  entries now record `CC-BY-4.0` instead of `unknown`. Third-party rows keep
  their upstream `license` value. Open conflict: WaxalNLP is CC-BY-SA-4.0
  (share-alike), and several sources are still `unknown`.

## 2026-08-13

- Added `Minervus00/dyula-speech-bible` (gated, train split only, validation
  generated with `--eval-size`). Transcript comparison found 1,949 internal
  duplicate rows and 3 overlaps with the previous `bambara_jula` release.
- `merged-bambara-dioula` has no per-row language label (`und`) and 9,495 exact
  transcript overlaps with the previous `bambara_jula` release, so
  `bambara_jula` deduplicates on text only, not `(language, text)`.

## 2026-08-10 -- 2026-08-11

- Builder added; manifest expanded. Published validation/dev/test splits are
  kept as validation; sources without one get a deterministic `--eval-size`
  holdout. Validation rows win during dedup, and the build fails if any key
  remains in both splits.
- FLEURS has no Dyula config; FLEURS `ff_sn` is Senegalese Fula, not the
  Burkina variety. Common Voice and SOREVA entries are commented out (removed
  from the Hub / need remote code).
- Several licenses are still `unknown` -- confirm before any public or
  commercial use.
