# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "datasets>=5.0.0",
#     "huggingface-hub>=0.25.0",
#     "pyarrow>=18.0.0",
#     "python-dotenv>=1.0.0",
#     "soundfile>=0.12.0",
# ]
# ///
"""Build the Zenodo 8320370 Dioula spoken-digits dataset and optionally push it to HF.

Source: https://zenodo.org/records/8320370 (CC-BY-4.0), a zip of zip
(data/8320370.zip -> AudiosDioula.zip -> Class_1..Class_4/*.wav), where each
class folder holds recordings of speakers saying that digit (1-4) in Dioula.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import random
import zipfile
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

import pyarrow as pa
import soundfile as sf
from datasets import Audio, ClassLabel, Dataset, DatasetDict, DatasetInfo, Features, Value
from datasets.table import InMemoryTable

load_dotenv()

SOURCE_URL = "https://zenodo.org/records/8320370"
SOURCE_DOI = "10.5281/zenodo.8320370"
LICENSE = "CC-BY-4.0"
ATTRIBUTION = (
    "KEITA Zakaria Cheick Oumar and BATONIO Fabrice (Universite de Bordeaux / UNB / ESI); "
    "data collection managed by NABALOUM Emile, project managers Dr SOME Borlli Michel and "
    "Dr DIALLO Gayo."
)
LANGUAGE = "dyu"
CONTENT_TYPE = "spoken-digit"
CLASS_LABELS = ["1", "2", "3", "4"]

AUDIO_PA_TYPE = pa.struct([pa.field("bytes", pa.binary()), pa.field("path", pa.string())])

FEATURES = Features(
    {
        "audio": Audio(decode=False),
        "text": Value("string"),
        "label": ClassLabel(names=CLASS_LABELS),
        "language": Value("string"),
        "duration": Value("float64"),
        "id": Value("string"),
        "content_type": Value("string"),
        "source": Value("string"),
        "license": Value("string"),
        "attribution": Value("string"),
        "source_url": Value("string"),
    }
)


def extract_raw(zip_path: Path, raw_dir: Path, *, force: bool) -> Path:
    audio_root = raw_dir / "AudiosDioula"
    if audio_root.is_dir() and not force:
        return audio_root

    raw_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as outer_zip:
        inner_name = next(
            name for name in outer_zip.namelist() if name.endswith("AudiosDioula.zip")
        )
        inner_bytes = outer_zip.read(inner_name)

    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zip:
        for member in inner_zip.infolist():
            if member.is_dir():
                continue
            if "__MACOSX" in member.filename or member.filename.endswith(".DS_Store"):
                continue
            if member.filename.endswith("readme.txt"):
                target = raw_dir / "AudiosDioula" / "readme.txt"
            else:
                target = raw_dir / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(inner_zip.read(member))

    return audio_root


def collect_rows(audio_root: Path) -> list[dict[str, object]]:
    rows = []
    for class_dir in sorted(audio_root.glob("Class_*")):
        if not class_dir.is_dir():
            continue
        digit = class_dir.name.removeprefix("Class_")
        if digit not in CLASS_LABELS:
            continue
        for wav_path in sorted(class_dir.glob("*.wav")):
            with sf.SoundFile(wav_path) as audio_file:
                duration = len(audio_file) / audio_file.samplerate
            rows.append(
                {
                    "path": wav_path,
                    "text": digit,
                    "label": digit,
                    "duration": round(duration, 3),
                    "id": f"dioula-digits:{class_dir.name}/{wav_path.stem}",
                }
            )
    return rows


def write_metadata_csv(rows: list[dict[str, object]], metadata_path: Path, repo_root: Path) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "text",
        "label",
        "language",
        "duration",
        "id",
        "content_type",
        "source",
        "license",
        "attribution",
        "source_url",
    ]
    with metadata_path.open("w", newline="", encoding="utf-8") as metadata_file:
        writer = csv.DictWriter(metadata_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            path: Path = row["path"]
            file_name = path.relative_to(repo_root) if path.is_absolute() else path
            writer.writerow(
                {
                    "file_name": file_name.as_posix(),
                    "text": row["text"],
                    "label": row["label"],
                    "language": LANGUAGE,
                    "duration": row["duration"],
                    "id": row["id"],
                    "content_type": CONTENT_TYPE,
                    "source": "zenodo-8320370",
                    "license": LICENSE,
                    "attribution": ATTRIBUTION,
                    "source_url": SOURCE_URL,
                }
            )


def build_dataset(rows: list[dict[str, object]]) -> Dataset:
    audio_values = []
    text_values = []
    label_values = []
    duration_values = []
    id_values = []
    for row in rows:
        path: Path = row["path"]
        audio_values.append({"bytes": path.read_bytes(), "path": path.name})
        text_values.append(row["text"])
        label_values.append(CLASS_LABELS.index(row["label"]))
        duration_values.append(row["duration"])
        id_values.append(row["id"])

    row_count = len(rows)
    table = pa.table(
        {
            "audio": pa.array(audio_values, type=AUDIO_PA_TYPE),
            "text": pa.array(text_values, type=pa.string()),
            "label": pa.array(label_values, type=pa.int64()),
            "language": pa.array([LANGUAGE] * row_count, type=pa.string()),
            "duration": pa.array(duration_values, type=pa.float64()),
            "id": pa.array(id_values, type=pa.string()),
            "content_type": pa.array([CONTENT_TYPE] * row_count, type=pa.string()),
            "source": pa.array(["zenodo-8320370"] * row_count, type=pa.string()),
            "license": pa.array([LICENSE] * row_count, type=pa.string()),
            "attribution": pa.array([ATTRIBUTION] * row_count, type=pa.string()),
            "source_url": pa.array([SOURCE_URL] * row_count, type=pa.string()),
        }
    )
    return Dataset(InMemoryTable(table), info=DatasetInfo(features=FEATURES))


def stratified_split(
    dataset: Dataset, *, eval_size: float, eval_split_name: str, seed: int
) -> DatasetDict:
    by_label: dict[int, list[int]] = {}
    for index, label in enumerate(dataset["label"]):
        by_label.setdefault(label, []).append(index)

    train_indices: list[int] = []
    eval_indices: list[int] = []
    rng = random.Random(seed)
    for label, indices in by_label.items():
        shuffled = indices[:]
        rng.shuffle(shuffled)
        eval_count = max(1, round(len(shuffled) * eval_size))
        eval_indices.extend(shuffled[:eval_count])
        train_indices.extend(shuffled[eval_count:])

    train_indices.sort()
    eval_indices.sort()
    return DatasetDict(
        {
            "train": dataset.select(train_indices),
            eval_split_name: dataset.select(eval_indices),
        }
    )


def print_summary(splits: DatasetDict) -> None:
    for split_name, split_dataset in splits.items():
        label_counts = Counter(split_dataset["label"])
        total_duration = sum(split_dataset["duration"])
        names = split_dataset.features["label"].names
        counts_by_name = {names[label]: count for label, count in sorted(label_counts.items())}
        print(
            f"split={split_name} rows={len(split_dataset)} duration_s={total_duration:.1f} "
            f"labels={counts_by_name}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip-path",
        type=Path,
        default=Path("data/8320370.zip"),
        help="Path to the downloaded Zenodo zip. Default: data/8320370.zip.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw_sources/dioula-digits"),
        help="Where to extract the raw archive. Default: data/raw_sources/dioula-digits.",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=Path("data/processed/dioula-digits/metadata.csv"),
        help="Where to write the provenance metadata.csv.",
    )
    parser.add_argument("--force-extract", action="store_true", help="Re-extract even if raw-dir exists.")
    parser.add_argument(
        "--output-parquet",
        type=Path,
        help="Optional directory to write train/validation parquet files for local inspection.",
    )
    parser.add_argument("--repo-id", help="Hugging Face dataset repo id to push to, e.g. madoss/faso-speech-dioula-digits.")
    parser.add_argument("--config-name", default="default", help="HF config name when pushing. Default: default.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for the stratified split. Default: 42.")
    parser.add_argument("--eval-size", type=float, default=0.1, help="Fraction per class held out for eval. Default: 0.1.")
    parser.add_argument("--eval-split-name", default="validation", help="Name of the held-out split. Default: validation.")
    parser.add_argument(
        "--readme",
        type=Path,
        help="Path to a dataset card to upload as README.md when pushing (requires --repo-id).",
    )
    parser.add_argument("--token-env", default="HF_TOKEN", help="Env var holding the HF token. Default: HF_TOKEN.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd()

    audio_root = extract_raw(args.zip_path, args.raw_dir, force=args.force_extract)
    rows = collect_rows(audio_root)
    if not rows:
        raise SystemExit(f"No wav files found under {audio_root}")
    print(f"collected {len(rows)} audio files under {audio_root}")

    write_metadata_csv(rows, args.metadata_path, repo_root)
    print(f"wrote provenance metadata to {args.metadata_path}")

    dataset = build_dataset(rows)
    splits = stratified_split(
        dataset,
        eval_size=args.eval_size,
        eval_split_name=args.eval_split_name,
        seed=args.seed,
    )
    print_summary(splits)

    if args.output_parquet:
        args.output_parquet.mkdir(parents=True, exist_ok=True)
        for split_name, split_dataset in splits.items():
            parquet_path = args.output_parquet / f"{split_name}.parquet"
            split_dataset.to_parquet(str(parquet_path))
            print(f"wrote {parquet_path}")

    if args.repo_id:
        token = os.environ.get(args.token_env) or None
        splits.push_to_hub(args.repo_id, config_name=args.config_name, token=token)
        print(f"url=https://huggingface.co/datasets/{args.repo_id}")
        print(f"config={args.config_name}")

        if args.readme:
            from huggingface_hub import HfApi

            HfApi(token=token).upload_file(
                path_or_fileobj=str(args.readme),
                path_in_repo="README.md",
                repo_id=args.repo_id,
                repo_type="dataset",
            )
            print(f"uploaded {args.readme} as README.md")


if __name__ == "__main__":
    main()
