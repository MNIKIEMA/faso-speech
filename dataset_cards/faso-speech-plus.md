---
license: other
language:
  - mos
  - dyu
  - und
  - ffm
  - fue
  - fuh
  - fuf
  - fuc
  - fui
  - fuq
  - fuv
  - ful
task_categories:
  - automatic-speech-recognition
pretty_name: Faso Speech Plus
tags:
  - audio
  - speech
  - asr
  - burkina-faso
  - moore
  - jula
  - fulfulde
configs:
  - config_name: moore
    data_files:
      - split: train
        path: moore/train.parquet
      - split: validation
        path: moore/validation.parquet
  - config_name: bambara_jula
    data_files:
      - split: train
        path: bambara_jula/train.parquet
      - split: validation
        path: bambara_jula/validation.parquet
  - config_name: fula
    data_files:
      - split: train
        path: fula/train.parquet
      - split: validation
        path: fula/validation.parquet
---

# Faso Speech Plus

Faso Speech Plus extends [`madoss/faso-speech`](https://huggingface.co/datasets/madoss/faso-speech)
by concatenating it with other already-published ASR datasets covering the
same target languages (Mooré, Jula, Fulfuldé), plus related language
varieties grouped by macrolanguage.

Built with `scripts/build_faso_speech_plus.py`. See that script's `MANIFEST`
for the authoritative, per-source list of dataset ids, column mappings,
target config, license, and attribution.

## Configs and dialect handling

| Config | Language group | Row-level `language` values |
| --- | --- | --- |
| `moore` | Mooré | `mos` (Mooré) |
| `bambara_jula` | Bambara and Jula | `dyu` (Jula/Dioula), `und` when the merged source does not identify the variety |
| `fula` | Fula | `ffm`, `fuc`, `fue`, `fuf`, `fuh`, `fui`, `fuq`, `fuv`, or `ful` when the precise variety is unknown |

Use the row-level `language` field to select a precise variety. Related
languages and varieties within a config should not be assumed interchangeable.

## Composition

| Config | Rows | Duration | Sources |
| --- | ---: | ---: | --- |
| `moore` | 37,977 | 98.46 hours | Faso Speech, AfriSpeech, Moore Bible |
| `bambara_jula` | 93,976 | 123.33 hours | Faso Speech, AfriSpeech, Koumankan4Dyula, Dyula Speech Bible, merged Bambara-Dioula |
| `fula` | 49,693 | 231.22 hours | Faso Speech, Omnilingual ASR, Fula-pular, WaxalNLP, FLEURS |

Total: **181,646 rows** and **453.01 hours**.

Before inclusion, `madoss/merged-bambara-dioula-dataset` contained 85,040 rows
but only 37,848 unique transcripts. Exact comparison found 9,495 transcripts
already present in the prior `bambara_jula` release. After global transcript
deduplication, it contributes 28,353 rows.

`Minervus00/dyula-speech-bible` contains 52,163 source rows and 50,214
unique transcripts. Exact transcript comparison found 1,949 internal duplicate
rows and 3 overlaps with the previous `bambara_jula` release. After global
deduplication, it contributes 50,211 rows. The source is gated and does not
declare a license, so its rows are recorded with license `unknown`.

## Data splits

Published validation splits are preserved for every source that provides one.
Configured upstream `dev` and `test` splits are combined into validation, never
training. For a source without evaluation data, the builder deterministically
holds out `--eval-size` of that source's training rows using `--seed`. Final
deduplication gives validation rows priority. It uses transcript-only matching
for `bambara_jula` because the merged source lacks per-row language labels, and
`(language, text)` matching for the other configs.
The completed build also verifies that no deduplication key remains in both
train and validation; the published `bambara_jula` files have zero transcript
overlap between those splits.

## Data Fields

Same compact schema as `faso-speech`, plus per-row provenance:

| Column | Description |
| --- | --- |
| `audio` | Embedded `Audio(decode=False)` value with `bytes` and `path` |
| `text` | Transcript |
| `language` | Precise ISO 639-3 code, a macrolanguage code, or `und` when the source does not identify Bambara versus Jula |
| `duration` | Chunk duration in seconds |
| `id` | Source-prefixed native identifier, or a generated 16-character hash |
| `content_type` | Source content type, or `external` when the source doesn't provide one |
| `speaker_id` | `<source>:<upstream speaker id>`, or null when the source has no speaker labels |
| `gender` | Speaker gender (`male`/`female`) when the source provides it, otherwise null |
| `source` | Manifest entry id this row came from (see `MANIFEST` in the build script) |
| `license` | License string recorded for that source in the manifest |
| `attribution` | Attribution string recorded for that source in the manifest |

## Licensing And Attribution

Faso Speech Plus aggregates sources under different licenses, so it has no
single license. Each row records its own terms in the `license`, `source`, and
`attribution` fields:

- `madoss/faso-speech` rows are CC-BY-4.0.
- Meta Omnilingual ASR Corpus and Google FLEURS rows are CC-BY-4.0.
- Google WaxalNLP rows are CC-BY-SA-4.0 (share-alike).
- Several sources do not declare a license and are recorded as `unknown`.

Filter on `license` to keep only the terms your use allows, and credit the
upstream source of every row you use. Users are responsible for verifying
that their intended use is permitted.
