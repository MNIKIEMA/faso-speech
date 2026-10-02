# Hugging Face export (`scripts/export_hf_audio_arrow.py`)

Builds `madoss/faso-speech` from `data/processed/metadata.csv`: embedded
`Audio(decode=False)`, compact training columns, one config per language,
deterministic 90/10 train/validation split.

## 2026-10-02

- Tagged the Hub repo `v1.0.0` at `fbc4118a` before adding columns.
- Export now joins `metadata/speakers.csv` on `catalog_id` and adds
  `speaker_id` and `gender` to the training columns (null when unknown).
  `--speakers PATH` overrides the file, `--no-speakers` restores the old
  schema. Any non-empty `speaker_id` is exported regardless of `status`, so
  the CSV is the only gate. Verified on the real metadata: 8,053 of 9,291
  rows get a speaker ID.
- Not yet re-published with the new columns; next release tag `v1.1.0`.

## 2026-06-14

- Segmentation is applied at export time: when an
  `inaSpeechSegmenter` segments CSV exists for a chunk, only padded speech
  ranges are embedded (defaults documented in `README_HF.md`); otherwise the
  original chunk audio is kept. Duration is recomputed from the kept ranges.
- Default export keeps only training columns; `--include-all-metadata` keeps
  everything.
