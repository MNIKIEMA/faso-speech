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
        # TODO: Skip rows shorter than 0.72 seconds by default, matching segmentation.
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

        columns[audio_column].append(
            {
                "bytes": audio_path.read_bytes(),
                "path": Path(relative_path).name,
            }
        )
        for column in metadata_columns:
            columns[column].append(row[column])

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
