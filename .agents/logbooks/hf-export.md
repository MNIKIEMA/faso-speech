# Hugging Face export (`scripts/export_hf_audio_arrow.py`)

Builds `madoss/faso-speech` from `data/processed/metadata.csv`: embedded
`Audio(decode=False)`, compact training columns, one config per language,
deterministic 90/10 train/validation split.

## 2026-10-02

- `gender` falls back to inaSpeechSegmenter when `speakers.csv` has none: the
  segmenter labels speech `male`/`female`, which `normalize_segment_label`
  used to collapse to `speech` before writing, so the 8,862 existing segment
  CSVs carry no gender. Segment CSVs now keep a `gender` column; the export
  takes the dominant gender over speech time if it covers >=
  `--gender-min-share` (0.8). Old CSVs without the column give null. Needs a
  re-run: `uv run faso-speech preprocess segments --refresh`.
- Speaker IDs cannot come from inaSpeechSegmenter (no speaker embedding /
  diarization); they stay manual in `metadata/speakers.csv`.
- `preprocess segments --dry-run` still writes `segmentation_log.csv` (default
  `data/processed/`), overwriting the previous run's log. Pass `--log` to a
  scratch path when only inspecting.
- Tagged the Hub repo `v1.0.0` at `fbc4118a` before adding columns.
- Export now joins `metadata/speakers.csv` on `catalog_id` and adds
  `speaker_id` and `gender` to the training columns (null when unknown).
  `--speakers PATH` overrides the file, `--no-speakers` restores the old
  schema. Any non-empty `speaker_id` is exported regardless of `status`, so
  the CSV is the only gate. Verified on the real metadata: 8,053 of 9,291
  rows get a speaker ID.
- Not yet re-published with the new columns; next release tag `v1.1.0`.
- License decided: CC-BY-4.0 for the faso-speech and dioula-digits cards (the Hub already said `cc-by-4.0`;
  the local card had `other`). Card now credits mooreburkina.com.
  faso-speech-plus stays `other` because it mixes licenses.

## 2026-06-14

- Segmentation is applied at export time: when an
  `inaSpeechSegmenter` segments CSV exists for a chunk, only padded speech
  ranges are embedded (defaults documented in `dataset_cards/faso-speech.md`); otherwise the
  original chunk audio is kept. Duration is recomputed from the kept ranges.
- Default export keeps only training columns; `--include-all-metadata` keeps
  everything.
