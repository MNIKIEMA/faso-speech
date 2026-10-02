---
license: cc-by-4.0
language:
  - dyu
  - bm
task_categories:
  - audio-classification
task_ids:
  - keyword-spotting
pretty_name: Faso Speech Dioula Digits
tags:
  - audio
  - speech
  - burkina-faso
  - dioula
  - bambara
  - digits
  - spoken-digits
  - classification
size_categories:
  - 1K<n<10K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train-*
      - split: validation
        path: data/validation-*
---

# Faso Speech Dioula Digits

A spoken-digit classification dataset in Dioula (Jula/Bambara), built from the
[Zenodo record 8320370](https://zenodo.org/records/8320370) archive
(DOI: [10.5281/zenodo.8320370](https://doi.org/10.5281/zenodo.8320370)).

Each clip is one speaker saying a single digit, 1 through 4, in Dioula.
Recordings vary in speaker, accent, and recording environment.

## Dataset Summary

| Split | Rows | Duration | Per-class rows |
| --- | ---: | ---: | --- |
| train | 1,532 | 01:34:14.9 | 383 / 383 / 383 / 383 |
| validation | 168 | 00:10:08.2 | 42 / 42 / 42 / 42 |

The split is a deterministic, per-class 90/10 hold-out (seed 42), so both
splits have an even class balance across digits 1-4.

## Data Fields

| Column | Description |
| --- | --- |
| `audio` | Embedded Hugging Face `Audio(decode=False)` value with `bytes` and `path` |
| `text` | The spoken digit as a string (`"1"`-`"4"`) |
| `label` | The spoken digit as a `ClassLabel` (`0`-`3`, names `"1"`-`"4"`) |
| `language` | `dyu` |
| `duration` | Clip duration in seconds |
| `id` | Stable identifier, `dioula-digits:Class_<n>/<original_file_stem>` |
| `content_type` | `spoken-digit` |
| `source` | `zenodo-8320370` |
| `license` | `CC-BY-4.0` |
| `attribution` | Source authors, see below |
| `source_url` | https://zenodo.org/records/8320370 |

## Usage

```python
from datasets import Audio, load_dataset

ds = load_dataset("madoss/faso-speech-dioula-digits")
ds = ds.cast_column("audio", Audio(decode=False))

print(ds["train"][0]["text"], ds["train"][0]["label"])
print(ds["train"][0]["audio"])
```

## Source Data

Original archive: `AudiosDioula.zip`, four folders `Class_1`-`Class_4`, one
`.wav` file per recording, no changes made to the audio itself. Rows were
grouped by folder into `label`/`text`.

Per the source README, the data was collected for the research project
*"Setting up a speech recognition model for under-resourced languages"*,
targeting a Dioula digit-recognition model.

## Licensing and Attribution

Licensed **CC-BY-4.0** by the original authors:

> KEITA Zakaria Cheick Oumar and BATONIO Fabrice (Universite de Bordeaux /
> UNB / ESI). Data collection managed by NABALOUM Emile, project managers
> Dr SOME Borlli Michel and Dr DIALLO Gayo.

If you use this dataset, please credit the original authors and cite the
Zenodo record (DOI 10.5281/zenodo.8320370) in addition to this repository.

## Related

Part of the [`madoss`](https://huggingface.co/madoss) Burkina Faso speech
data efforts, alongside
[`madoss/faso-speech`](https://huggingface.co/datasets/madoss/faso-speech)
and [`madoss/faso-speech-plus`](https://huggingface.co/datasets/madoss/faso-speech-plus).
Kept as a separate repo because it is digit classification, not sentence-level
ASR, and carries a clear CC-BY-4.0 license.
