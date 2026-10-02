---
license: cc-by-4.0
language:
  - mos
  - dyu
  - ff
  - fr
task_categories:
  - automatic-speech-recognition
task_ids:
  - speech-recognition
pretty_name: Faso Speech
tags:
  - audio
  - speech
  - asr
  - burkina-faso
  - moore
  - dioula
  - fulfulde
configs:
  - config_name: moore
  - config_name: dioula
  - config_name: fulfulde
---

# Faso Speech

Faso Speech is a speech dataset built for Burkina Faso languages, starting with
paired audio and text from Moore Burkina resources.

The current target languages are:

- Moore
- Dioula
- Fulfulde

French rows are preserved when they appear in the processed source material,
mostly as translation or supporting content.

## Dataset Summary

The dataset contains short audio chunks paired with transcripts. Source pages
were archived separately, then processed into timed candidate chunks for ASR
training and review.

The first source family is Moore Burkina. Many records embed or link IPS
app-builder pages hosted on `media.ipsapps.org`; those pages expose timing
arrays, text blocks, audio URLs, and next-page links used during extraction.

## Current Processed Totals

These totals describe the processed dataset metadata used for this release.

| Language | Rows | Duration | Rows shorter than 0.72s |
| --- | ---: | ---: | ---: |
| moore | 5,746 | 05:41:41.870 | 88 |
| fulfulde | 2,260 | 02:41:47.140 | 103 |
| dioula | 1,073 | 00:49:45.910 | 26 |
| french | 212 | 00:12:23.400 | 4 |

## Configurations

Use one configuration per primary language:

- `moore`
- `dioula`
- `fulfulde`

Each configuration has deterministic `train` and `validation` splits. The
split ratio is 90% train and 10% validation.

## Data Fields

The dataset uses a compact ASR-oriented schema:

| Column | Description |
| --- | --- |
| `audio` | Embedded Hugging Face `Audio(decode=False)` value with `bytes` and `path` |
| `text` | Transcript |
| `language` | Language label |
| `duration` | Chunk duration from metadata |
| `chunk_id` | Stable chunk identifier |
| `record_id` | Source record identifier |
| `content_type` | Source content type |
| `speaker_id` | Opaque per-speaker identifier from `metadata/speakers.csv`, or null when the reader is unknown |
| `gender` | Speaker gender (`male`/`female`): from `metadata/speakers.csv` when the speaker is known, otherwise predicted by inaSpeechSegmenter when one gender covers at least 80% of the chunk's speech; null otherwise |

## Usage

```python
from datasets import Audio, load_dataset

ds = load_dataset("madoss/faso-speech", "moore")
ds = ds.cast_column("audio", Audio(decode=False))

print(ds["train"][0]["text"])
print(ds["train"][0]["audio"])
```

## Audio Preparation

The dataset is distributed as embedded Hugging Face `Audio(decode=False)`
examples. When segment metadata was available during preparation, only detected
speech ranges were embedded, with small padding around speech to avoid clipping
words. Rows without segment metadata keep their original chunk audio.

Preparation used the following default padding and merge behavior:

| Option | Default |
| --- | ---: |
| `--segment-start-padding` | 0.15 |
| `--segment-end-padding` | 0.25 |
| `--music-start-padding` | 0.05 |
| `--music-end-padding` | 0.05 |
| `--max-intra-segment-gap` | 0.50 |
| `--max-music-gap` | 0.05 |

## Source Data And Provenance

The source archive preserves raw source artifacts separately from processed
training examples, including source URLs, app-builder HTML, optional wrapper
HTML, audio URLs, downloaded audio, extracted text blocks, timing metadata,
language labels, content type, and metadata.

This separation keeps the processed dataset traceable to the original source
material.

## Licensing And Attribution

Faso Speech is released under the
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
license.

The audio and texts come from [mooreburkina.com](https://mooreburkina.com).
When you use or redistribute the dataset, credit both Faso Speech and
mooreburkina.com, and keep the per-record provenance where possible.
