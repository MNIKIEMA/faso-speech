# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "datasets>=5.0.0",
#     "pyarrow>=18.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
from __future__ import annotations

import argparse
import csv
import os
import random
import subprocess
from pathlib import Path

from dotenv import load_dotenv

import pyarrow as pa
from datasets import Audio, Dataset, DatasetInfo, Features, Value
from datasets.dataset_dict import DatasetDict
from datasets.table import InMemoryTable

load_dotenv()

AUDIO_PA_TYPE = pa.struct(
    [
        pa.field("bytes", pa.binary()),
        pa.field("path", pa.string()),
    ]
)
TRAINING_COLUMNS = [
    "text",
    "language",
    "duration",
    "chunk_id",
    "record_id",
    "content_type",
]
SEGMENT_START_PADDING = 0.15
SEGMENT_END_PADDING = 0.25
MUSIC_START_PADDING = 0.05
MUSIC_END_PADDING = 0.05
MAX_INTRA_SEGMENT_GAP = 0.50
MAX_MUSIC_GAP = 0.05


def read_metadata(metadata_path: Path) -> list[dict[str, str]]:
    with metadata_path.open(newline="", encoding="utf-8") as metadata_file:
        return list(csv.DictReader(metadata_file))


def infer_file_column(rows: list[dict[str, str]], file_column: str | None) -> str:
    if file_column:
        if file_column not in rows[0]:
            raise SystemExit(f"Missing required column {file_column!r} in metadata")
        return file_column

    for candidate in ("file_name", "chunk_audio"):
        if candidate in rows[0]:
            return candidate
    raise SystemExit("Metadata must include a file_name or chunk_audio column")


def filter_rows(
    rows: list[dict[str, str]],
    *,
    languages: set[str],
    content_types: set[str],
    limit: int,
) -> list[dict[str, str]]:
    filtered = []
    for row in rows:
        if languages and row.get("language") not in languages:
            continue
        if content_types and row.get("content_type") not in content_types:
            continue
        filtered.append(row)
        if limit > 0 and len(filtered) >= limit:
            break
    return filtered


def resolve_audio_path(input_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    candidates = [
        path,
        input_dir / path,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Audio file not found: {path_value}")


def normalize_segment_label(label: str) -> str:
    normalized = label.strip()
    if normalized in {"speech", "male", "female"}:
        return "speech"
    if normalized.lower() in {"noenergy", "no_energy", "silence"}:
        return "noise"
    return normalized


def resolve_segments_path(input_dir: Path, row: dict[str, str], audio_path: Path) -> Path | None:
    candidates = []
    chunk_id = row.get("chunk_id", "").strip()
    language = row.get("language", "").strip()
    content_type = row.get("content_type", "").strip()
    if chunk_id and language and content_type:
        candidates.append(input_dir / language / content_type / "segments" / f"{chunk_id}.segments.csv")
    candidates.append(audio_path.with_suffix(".segments.csv"))

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def read_segments(segments_path: Path) -> list[dict[str, float | str]]:
    segments = []
    with segments_path.open(newline="", encoding="utf-8") as segments_file:
        for row in csv.DictReader(segments_file):
            label = normalize_segment_label(row.get("label", ""))
            start = float(row["start"])
            end = float(row["end"])
            if end <= start:
                continue
            segments.append({"label": label, "start": start, "end": end})
    return segments


def padded_speech_ranges(
    segments: list[dict[str, float | str]],
    *,
    start_padding: float,
    end_padding: float,
    music_start_padding: float,
    music_end_padding: float,
) -> list[tuple[float, float]]:
    ranges = []
    for index, segment in enumerate(segments):
        if segment["label"] != "speech":
            continue
        start = float(segment["start"])
        end = float(segment["end"])
        previous_segment = segments[index - 1] if index > 0 else None
        next_segment = segments[index + 1] if index + 1 < len(segments) else None

        effective_start_padding = start_padding
        if previous_segment and previous_segment["label"] == "music":
            effective_start_padding = min(start_padding, music_start_padding)

        effective_end_padding = end_padding
        if next_segment and next_segment["label"] == "music":
            effective_end_padding = min(end_padding, music_end_padding)

        ranges.append((max(0.0, start - effective_start_padding), end + effective_end_padding))
    return ranges


def labels_between(
    segments: list[dict[str, float | str]],
    start: float,
    end: float,
) -> set[str]:
    labels = set()
    for segment in segments:
        segment_start = float(segment["start"])
        segment_end = float(segment["end"])
        if segment_end <= start or segment_start >= end:
            continue
        labels.add(str(segment["label"]))
    return labels


def merge_ranges(
    ranges: list[tuple[float, float]],
    segments: list[dict[str, float | str]],
    *,
    max_intra_segment_gap: float,
    max_music_gap: float,
) -> list[tuple[float, float]]:
    if not ranges:
        return []

    merged = [ranges[0]]
    for start, end in ranges[1:]:
        previous_start, previous_end = merged[-1]
        gap = start - previous_end
        if gap <= 0:
            merged[-1] = (previous_start, max(previous_end, end))
            continue

        gap_labels = labels_between(segments, previous_end, start)
        max_gap = max_music_gap if "music" in gap_labels else max_intra_segment_gap
        if gap <= max_gap:
            merged[-1] = (previous_start, end)
            continue

        merged.append((start, end))
    return merged


def export_ranges_from_segments(
    segments_path: Path,
    *,
    start_padding: float,
    end_padding: float,
    music_start_padding: float,
    music_end_padding: float,
    max_intra_segment_gap: float,
    max_music_gap: float,
) -> list[tuple[float, float]]:
    segments = read_segments(segments_path)
    ranges = padded_speech_ranges(
        segments,
        start_padding=start_padding,
        end_padding=end_padding,
        music_start_padding=music_start_padding,
        music_end_padding=music_end_padding,
    )
    return merge_ranges(
        ranges,
        segments,
        max_intra_segment_gap=max_intra_segment_gap,
        max_music_gap=max_music_gap,
    )


def segment_audio_bytes(audio_path: Path, ranges: list[tuple[float, float]]) -> bytes:
    if not ranges:
        raise ValueError("At least one speech range is required.")

    trim_filters = []
    concat_inputs = []
    for index, (start, end) in enumerate(ranges):
        trim_filters.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]"
        )
        concat_inputs.append(f"[a{index}]")
    filter_complex = (
        ";".join(trim_filters)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={len(ranges)}:v=0:a=1[out]"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        "pipe:1",
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    return result.stdout


def audio_payload(
    input_dir: Path,
    row: dict[str, str],
    audio_path: Path,
    relative_path: str,
    *,
    apply_segments: bool,
    segment_start_padding: float = SEGMENT_START_PADDING,
    segment_end_padding: float = SEGMENT_END_PADDING,
    music_start_padding: float = MUSIC_START_PADDING,
    music_end_padding: float = MUSIC_END_PADDING,
    max_intra_segment_gap: float = MAX_INTRA_SEGMENT_GAP,
    max_music_gap: float = MAX_MUSIC_GAP,
) -> tuple[dict[str, bytes | str], dict[str, str]]:
    if not apply_segments:
        return {"bytes": audio_path.read_bytes(), "path": Path(relative_path).name}, row

    segments_path = resolve_segments_path(input_dir, row, audio_path)
    if not segments_path:
        return {"bytes": audio_path.read_bytes(), "path": Path(relative_path).name}, row

    export_ranges = export_ranges_from_segments(
        segments_path,
        start_padding=segment_start_padding,
        end_padding=segment_end_padding,
        music_start_padding=music_start_padding,
        music_end_padding=music_end_padding,
        max_intra_segment_gap=max_intra_segment_gap,
        max_music_gap=max_music_gap,
    )
    if not export_ranges:
        return {"bytes": audio_path.read_bytes(), "path": Path(relative_path).name}, row

    export_row = dict(row)
    speech_duration = sum(end - start for start, end in export_ranges)
    if "duration" in export_row:
        export_row["duration"] = str(round(speech_duration, 3))

    return (
        {
            "bytes": segment_audio_bytes(audio_path, export_ranges),
            "path": f"{Path(relative_path).stem}.segmented.wav",
        },
        export_row,
    )


def build_dataset(
    input_dir: Path,
    *,
    metadata_name: str = "metadata.csv",
    file_column: str | None = None,
    audio_column: str = "audio",
    languages: set[str] | None = None,
    content_types: set[str] | None = None,
    metadata_columns: list[str] | None = None,
    include_all_metadata: bool = False,
    limit: int = 0,
    apply_segments: bool = True,
    segment_start_padding: float = SEGMENT_START_PADDING,
    segment_end_padding: float = SEGMENT_END_PADDING,
    music_start_padding: float = MUSIC_START_PADDING,
    music_end_padding: float = MUSIC_END_PADDING,
    max_intra_segment_gap: float = MAX_INTRA_SEGMENT_GAP,
    max_music_gap: float = MAX_MUSIC_GAP,
) -> Dataset:
    metadata_path = input_dir / metadata_name
    rows = read_metadata(metadata_path)
    if not rows:
        raise SystemExit(f"No rows found in {metadata_path}")
    file_column = infer_file_column(rows, file_column)
    rows = filter_rows(
        rows,
        languages=languages or set(),
        content_types=content_types or set(),
        limit=limit,
    )
    if not rows:
        raise SystemExit(f"No matching rows found in {metadata_path}")

    columns: dict[str, list[object]] = {audio_column: []}
    if include_all_metadata:
        metadata_columns = [column for column in rows[0] if column != file_column]
    elif metadata_columns is None:
        metadata_columns = [column for column in TRAINING_COLUMNS if column in rows[0]]
    for column in metadata_columns:
        columns[column] = []

    for row in rows:
        relative_path = row[file_column]
        audio_path = resolve_audio_path(input_dir, relative_path)
        payload, export_row = audio_payload(
            input_dir,
            row,
            audio_path,
            relative_path,
            apply_segments=apply_segments,
            segment_start_padding=segment_start_padding,
            segment_end_padding=segment_end_padding,
            music_start_padding=music_start_padding,
            music_end_padding=music_end_padding,
            max_intra_segment_gap=max_intra_segment_gap,
            max_music_gap=max_music_gap,
        )

        columns[audio_column].append(payload)
        for column in metadata_columns:
            columns[column].append(export_row[column])

    arrow_columns = {
        audio_column: pa.array(columns[audio_column], type=AUDIO_PA_TYPE),
    }
    for column in metadata_columns:
        arrow_columns[column] = pa.array(columns[column], type=pa.string())

    table = pa.table(arrow_columns)
    features = Features(
        {
            audio_column: Audio(decode=False),
            **{column: Value("string") for column in metadata_columns},
        }
    )
    return Dataset(InMemoryTable(table), info=DatasetInfo(features=features))


def split_dataset(
    dataset: Dataset,
    *,
    eval_size: float,
    eval_split_name: str,
    seed: int,
) -> DatasetDict:
    if eval_size <= 0:
        return DatasetDict({"train": dataset})
    if eval_size >= 1:
        raise SystemExit("--eval-size must be less than 1.0")
    if eval_split_name == "train":
        raise SystemExit("--eval-split-name cannot be train")

    total = len(dataset)
    if total < 2:
        return DatasetDict({"train": dataset})

    eval_count = max(1, round(total * eval_size))
    eval_count = min(eval_count, total - 1)
    indices = list(range(total))
    random.Random(seed).shuffle(indices)
    eval_indices = set(indices[:eval_count])
    train_indices = [index for index in range(total) if index not in eval_indices]
    ordered_eval_indices = [index for index in range(total) if index in eval_indices]
    return DatasetDict(
        {
            "train": dataset.select(train_indices),
            eval_split_name: dataset.select(ordered_eval_indices),
        }
    )


def preview_dataset(dataset: Dataset, audio_column: str) -> None:
    print(dataset)
    print(f"features={dataset.features}")
    first_row = dict(dataset[0])
    first_audio = first_row[audio_column]
    first_row[audio_column] = {
        "bytes": f"<{len(first_audio['bytes'])} bytes>",
        "path": first_audio["path"],
    }
    print(f"first_row={first_row}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an embedded Hugging Face Audio dataset from audio files and metadata.csv."
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing metadata.csv and audio files.")
    parser.add_argument(
        "--metadata-name",
        default="metadata.csv",
        help="Metadata filename inside input_dir. Default: metadata.csv.",
    )
    parser.add_argument(
        "--file-column",
        help="Metadata column containing audio paths. Default: auto-detect file_name or chunk_audio.",
    )
    parser.add_argument("--language", action="append", help="Keep only this language. May be repeated.")
    parser.add_argument(
        "--content-type",
        action="append",
        help="Keep only this content type. May be repeated.",
    )
    parser.add_argument(
        "--column",
        action="append",
        help="Metadata column to keep. May be repeated. Default: training columns only.",
    )
    parser.add_argument(
        "--include-all-metadata",
        action="store_true",
        help="Keep every metadata column instead of the default training columns.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to export. Default: all.")
    parser.add_argument(
        "--audio-column",
        default="audio",
        help="Output Audio column name. Default: audio.",
    )
    parser.add_argument(
        "--no-apply-segments",
        action="store_true",
        help="Ignore segment CSVs and export original audio bytes.",
    )
    parser.add_argument(
        "--segment-start-padding",
        type=float,
        default=SEGMENT_START_PADDING,
        help="Seconds of real audio to keep before speech. Default: 0.15.",
    )
    parser.add_argument(
        "--segment-end-padding",
        type=float,
        default=SEGMENT_END_PADDING,
        help="Seconds of real audio to keep after speech. Default: 0.25.",
    )
    parser.add_argument(
        "--music-start-padding",
        type=float,
        default=MUSIC_START_PADDING,
        help="Maximum seconds to pad into music before speech. Default: 0.05.",
    )
    parser.add_argument(
        "--music-end-padding",
        type=float,
        default=MUSIC_END_PADDING,
        help="Maximum seconds to pad into music after speech. Default: 0.05.",
    )
    parser.add_argument(
        "--max-intra-segment-gap",
        type=float,
        default=MAX_INTRA_SEGMENT_GAP,
        help="Keep non-music gaps between speech ranges up to this many seconds. Default: 0.50.",
    )
    parser.add_argument(
        "--max-music-gap",
        type=float,
        default=MAX_MUSIC_GAP,
        help="Keep music gaps between speech ranges up to this many seconds. Default: 0.05.",
    )
    parser.add_argument(
        "--output-parquet",
        type=Path,
        help="Optional Parquet directory to write train.parquet and validation.parquet.",
    )
    parser.add_argument("--repo-id", help="Optional Hugging Face dataset repo id to push to.")
    parser.add_argument(
        "--config-name",
        default="default",
        help="Hugging Face dataset config name when pushing. Default: default.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for train/test split. Default: 42.")
    parser.add_argument(
        "--eval-size",
        type=float,
        default=0.1,
        help="Fraction kept for validation/eval split. Default: 0.1.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        dest="eval_size",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--eval-split-name",
        default="validation",
        help="Name for the held-out split. Default: validation.",
    )
    parser.add_argument(
        "--set-default",
        action="store_true",
        help="Mark this config as the default config on the Hub.",
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable containing the Hugging Face token. Default: HF_TOKEN.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = build_dataset(
        args.input_dir,
        metadata_name=args.metadata_name,
        file_column=args.file_column,
        audio_column=args.audio_column,
        languages=set(args.language or []),
        content_types=set(args.content_type or []),
        metadata_columns=args.column,
        include_all_metadata=args.include_all_metadata,
        limit=args.limit,
        apply_segments=not args.no_apply_segments,
        segment_start_padding=args.segment_start_padding,
        segment_end_padding=args.segment_end_padding,
        music_start_padding=args.music_start_padding,
        music_end_padding=args.music_end_padding,
        max_intra_segment_gap=args.max_intra_segment_gap,
        max_music_gap=args.max_music_gap,
    )
    splits = split_dataset(
        dataset,
        eval_size=args.eval_size,
        eval_split_name=args.eval_split_name,
        seed=args.seed,
    )
    print(splits)
    for split_name, split_dataset_item in splits.items():
        print(f"{split_name}_rows={len(split_dataset_item)}")
    preview_dataset(splits["train"], args.audio_column)

    if args.output_parquet:
        args.output_parquet.mkdir(parents=True, exist_ok=True)
        for split_name, split_dataset_item in splits.items():
            parquet_path = args.output_parquet / f"{split_name}.parquet"
            split_dataset_item.to_parquet(str(parquet_path))
            print(f"{split_name}_parquet={parquet_path}")

    if args.repo_id:
        splits.push_to_hub(
            args.repo_id,
            config_name=args.config_name,
            set_default=args.set_default or None,
            token=os.environ.get(args.token_env) or None,
        )
        print(f"url=https://huggingface.co/datasets/{args.repo_id}")
        print(f"config={args.config_name}")


if __name__ == "__main__":
    main()
