# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "datasets>=5.0.0",
#     "pyarrow>=18.0.0",
#     "python-dotenv>=1.0.0",
#     "soundfile>=0.12.0",
# ]
# ///
from __future__ import annotations

import argparse
import hashlib
import io
import os
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

import soundfile as sf
from datasets import (
    Audio,
    Dataset,
    Features,
    Value,
    concatenate_datasets,
    get_dataset_split_names,
    load_dataset,
)

load_dotenv()

COMMON_FEATURES = Features(
    {
        "audio": Audio(decode=False),
        "text": Value("string"),
        "language": Value("string"),
        "duration": Value("float64"),
        "id": Value("string"),
        "content_type": Value("string"),
        "source": Value("string"),
        "license": Value("string"),
        "attribution": Value("string"),
    }
)


OMNILINGUAL_FULA_VARIANTS = {
    "ffm": "Maasina Fulfulde",
    "fuc": "Pulaar",
    "fue": "Borgu Fulfulde",
    "fuf": "Pular",
    "fuh": "Western Niger Fulfulde",
    "fui": "Bagirmi Fulfulde",
    "fuq": "Central-Eastern Niger Fulfulde",
    "fuv": "Nigerian Fulfulde",
}


@dataclass
class ExternalSource:
    id: str
    hf_dataset_id: str
    hf_config: str | None
    hf_split: str
    target_config: str
    language: str
    audio_column: str
    text_column: str
    license: str
    attribution: str
    eval_splits: tuple[str, ...] = ()
    verified: bool = False
    notes: str = ""


MANIFEST: list[ExternalSource] = [
    ExternalSource(
        id="faso-speech-moore",
        hf_dataset_id="madoss/faso-speech",
        hf_config="moore",
        hf_split="train",
        target_config="moore",
        language="mos",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="madoss/faso-speech (mooreburkina.com)",
        verified=True,
    ),
    ExternalSource(
        id="faso-speech-dioula",
        hf_dataset_id="madoss/faso-speech",
        hf_config="dioula",
        hf_split="train",
        target_config="bambara_jula",
        language="dyu",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="madoss/faso-speech (mooreburkina.com)",
        verified=True,
    ),
    ExternalSource(
        id="faso-speech-fulfulde",
        hf_dataset_id="madoss/faso-speech",
        hf_config="fulfulde",
        hf_split="train",
        target_config="fula",
        language="fuh",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="madoss/faso-speech (mooreburkina.com)",
        verified=True,
    ),
    ExternalSource(
        id="afrispeech-moore",
        hf_dataset_id="AfriSpeech/african-speech-public_v1",
        hf_config="moore_mos",
        hf_split="train",
        target_config="moore",
        language="mos",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="AfriSpeech/african-speech-public_v1, Moore",
        verified=True,
        notes="Schema verified from the published Parquet conversion; may overlap religious sources.",
    ),
    ExternalSource(
        id="afrispeech-jula",
        hf_dataset_id="AfriSpeech/african-speech-public_v1",
        hf_config="jula_dyu",
        hf_split="train",
        target_config="bambara_jula",
        language="dyu",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="AfriSpeech/african-speech-public_v1, Jula",
        verified=True,
        notes="Schema and config verified from the published Parquet index.",
    ),
    *[
        ExternalSource(
            id=f"omnilingual-{language}",
            hf_dataset_id="facebook/omnilingual-asr-corpus",
            hf_config=f"{language}_Latn",
            hf_split="train",
            target_config="fula",
            language=language,
            audio_column="audio",
            text_column="raw_text",
            license="CC-BY-4.0",
            attribution=f"Meta Omnilingual ASR Corpus, {variant_name}",
            verified=True,
            notes="Published train split; validation is generated with --eval-size.",
        )
        for language, variant_name in OMNILINGUAL_FULA_VARIANTS.items()
    ],
    ExternalSource(
        id="moore-bible",
        hf_dataset_id="madoss/moore_audio_data",
        hf_config=None,
        hf_split="train",
        target_config="moore",
        language="mos",
        audio_column="audio",
        text_column="text",
        license="unknown",
        attribution="madoss/moore_audio_data (Bible audio)",
        verified=True,
        notes="Schema verified from the published Parquet metadata; license is not declared.",
    ),
    ExternalSource(
        id="koumankan4dyula",
        hf_dataset_id="uvci/koumankan4dyula",
        hf_config=None,
        hf_split="train",
        target_config="bambara_jula",
        language="dyu",
        audio_column="audio",
        text_column="dyu",
        license="unknown",
        attribution="UVCI Koumankan4Dyula",
        eval_splits=("dev", "test"),
        verified=True,
        notes="Schema and all three published splits verified; Hub access approval is required.",
    ),
    ExternalSource(
        id="merged-bambara-dioula",
        hf_dataset_id="madoss/merged-bambara-dioula-dataset",
        hf_config=None,
        hf_split="train",
        target_config="bambara_jula",
        language="und",
        audio_column="audio",
        text_column="transcription",
        license="unknown",
        attribution="madoss/merged-bambara-dioula-dataset",
        eval_splits=("validation", "test"),
        verified=True,
        notes=(
            "Mixed Bambara/Jula corpus without a per-row language label. Exact transcript "
            "comparison found 9,495 overlaps with the previous bambara_jula release."
        ),
    ),
    ExternalSource(
        id="fleurs-dyu",
        hf_dataset_id="google/fleurs",
        hf_config="dyu_bj",
        hf_split="train",
        target_config="bambara_jula",
        language="dyu",
        audio_column="audio",
        text_column="transcription",
        license="CC-BY-4.0",
        attribution="Google FLEURS, Jula",
        notes="Not available: FLEURS does not publish a Dyula/Jula configuration.",
    ),
    # ExternalSource(
    #     id="dioula-bambara-cv",
    #     hf_dataset_id="mozilla-foundation/common_voice_17_0",
    #     hf_config="bm",
    #     hf_split="train",
    #     target_config="bambara_jula",
    #     language="bam",
    #     audio_column="audio",
    #     text_column="sentence",
    #     license="CC0-1.0 (Common Voice default, verify per-clip)",
    #     attribution="Mozilla Common Voice 17.0, Bambara",
    #     notes="Gated dataset: requires accepting Hub terms and an HF_TOKEN with access.",
    # ),
    ExternalSource(
        id="fula-pular",
        hf_dataset_id="Pullo-Africa-Protagonist/Fula-pular",
        hf_config=None,
        hf_split="train",
        target_config="fula",
        language="fuf",
        audio_column="path",
        text_column="text",
        license="unknown",
        attribution="Pullo-Africa-Protagonist/Fula-pular",
        verified=True,
        notes="Schema verified. Different Fula variant than the BF target dialect.",
    ),
    ExternalSource(
        id="waxalnlp-ful",
        hf_dataset_id="google/WaxalNLP",
        hf_config="ful_asr",
        hf_split="train",
        target_config="fula",
        language="ful",
        audio_column="audio",
        text_column="transcription",
        license="CC-BY-SA-4.0",
        attribution="Google WaxalNLP, Fula",
        eval_splits=("validation", "test"),
        verified=True,
        notes="Fula ASR config and schema verified; the unlabeled split is intentionally excluded.",
    ),
    # ExternalSource(
    #     id="soreva",
    #     hf_dataset_id="OlameMend/soreva",
    #     hf_config=None,
    #     hf_split="train",
    #     target_config="fula",
    #     language="ful",
    #     audio_column="audio",
    #     text_column="text",
    #     license="unknown",
    #     attribution="OlameMend/soreva",
    # ),
    # commented because it require python code execution on the HF side
    ExternalSource(
        id="fleurs-ff",
        hf_dataset_id="google/fleurs",
        hf_config="ff_sn",
        hf_split="train",
        target_config="fula",
        language="fuc",
        audio_column="audio",
        text_column="transcription",
        license="CC-BY-4.0",
        attribution="Google FLEURS, Fulfulde",
        eval_splits=("validation", "test"),
        verified=True,
        notes="Schema and config verified; Senegalese Fula rather than the Burkina Faso dialect.",
    ),
    # ExternalSource(
    #     id="common-voice-ff",
    #     hf_dataset_id="mozilla-foundation/common_voice_17_0",
    #     hf_config="ff",
    #     hf_split="train",
    #     target_config="fula",
    #     language="ful",
    #     audio_column="audio",
    #     text_column="sentence",
    #     license="CC0-1.0 (Common Voice default, verify per-clip)",
    #     attribution="Mozilla Common Voice 17.0, Fula",
    #     notes="Gated dataset: requires accepting Hub terms and an HF_TOKEN with access.",
    # ),
    # Not available on HF hub anymore
]


def audio_duration_seconds(audio_bytes: bytes) -> float:
    with sf.SoundFile(io.BytesIO(audio_bytes)) as audio_file:
        return len(audio_file) / audio_file.samplerate


def example_id(entry: ExternalSource, row: dict, audio_value: dict) -> str:
    native_id = row.get("id") or row.get("chunk_id")
    if native_id not in (None, ""):
        return f"{entry.id}:{native_id}"

    text = str(row.get(entry.text_column) or "").strip().encode("utf-8")
    audio_identity = audio_value.get("bytes") or str(audio_value.get("path") or "").encode("utf-8")
    identity = entry.id.encode("utf-8") + b"\0" + text + b"\0" + audio_identity
    return hashlib.sha1(identity).hexdigest()[:16]


def load_split(
    entry: ExternalSource, *, split: str, limit: int, token: str | None
) -> Dataset:
    requested_split = f"{split}[:{limit}]" if limit > 0 else split
    load_kwargs: dict[str, object] = {"split": requested_split, "token": token}
    if entry.hf_config:
        load_kwargs["name"] = entry.hf_config
    return load_dataset(entry.hf_dataset_id, **load_kwargs)


def concatenate_splits(datasets: list[Dataset]) -> Dataset:
    if not datasets:
        raise ValueError("At least one dataset split is required")
    return concatenate_datasets(datasets) if len(datasets) > 1 else datasets[0]


def normalize_source(
    entry: ExternalSource, *, split: str, limit: int, token: str | None
) -> Dataset:
    dataset = load_split(entry, split=split, limit=limit, token=token)
    dataset = dataset.cast_column(entry.audio_column, Audio(decode=False))

    def to_common_schema(row: dict) -> dict:
        audio_value = row[entry.audio_column]
        duration_value = row.get("duration")
        duration = (
            float(duration_value)
            if duration_value not in (None, "")
            else audio_duration_seconds(audio_value["bytes"])
        )
        return {
            "audio": audio_value,
            "text": str(row[entry.text_column]).strip(),
            "language": entry.language,
            "duration": round(duration, 3),
            "id": example_id(entry, row, audio_value),
            "content_type": str(row.get("content_type") or "external"),
            "source": entry.id,
            "license": entry.license,
            "attribution": entry.attribution,
        }

    normalized = dataset.map(
        to_common_schema,
        remove_columns=dataset.column_names,
    )
    return normalized.cast(COMMON_FEATURES)


def dedup_train_validation(
    train: Dataset, validation: Dataset, *, text_only: bool = False
) -> tuple[Dataset, Dataset]:
    """Deduplicate globally while giving published validation rows priority."""
    seen: set[str | tuple[str, str]] = set()

    def keep(row: dict) -> bool:
        key = row["text"] if text_only else (row["language"], row["text"])
        if key in seen:
            return False
        seen.add(key)
        return True

    before = len(train) + len(validation)
    validation = validation.filter(keep)
    train = train.filter(keep)
    dropped = before - len(train) - len(validation)
    if dropped:
        key_name = "text" if text_only else "(language, text)"
        print(f"  dedup: dropped {dropped} duplicate {key_name} rows")
    return train, validation


def split_dataset(
    dataset: Dataset,
    *,
    eval_size: float,
    eval_split_name: str,
    seed: int,
) -> dict[str, Dataset]:
    if eval_size <= 0:
        return {"train": dataset}
    if eval_size >= 1:
        raise SystemExit("--eval-size must be less than 1.0")

    total = len(dataset)
    if total < 2:
        return {"train": dataset}

    eval_count = max(1, round(total * eval_size))
    eval_count = min(eval_count, total - 1)
    indices = list(range(total))
    random.Random(seed).shuffle(indices)
    eval_indices = set(indices[:eval_count])
    train_indices = [index for index in range(total) if index not in eval_indices]
    ordered_eval_indices = [index for index in range(total) if index in eval_indices]
    return {
        "train": dataset.select(train_indices),
        eval_split_name: dataset.select(ordered_eval_indices),
    }


def print_summary(config_name: str, dataset: Dataset) -> None:
    total_duration = sum(dataset["duration"])
    source_counts = Counter(dataset["source"])
    license_counts = Counter(dataset["license"])
    print(f"config={config_name} rows={len(dataset)} duration_s={total_duration:.1f}")
    for source, count in sorted(source_counts.items()):
        print(f"  source={source} rows={count}")
    print(f"  licenses={dict(license_counts)}")


def inspect_source(entry: ExternalSource, *, token: str | None) -> None:
    if not entry.hf_dataset_id:
        print(f"{entry.id}: skipped, no hf_dataset_id set ({entry.notes or 'needs manual lookup'})")
        return

    load_kwargs: dict[str, object] = {"split": entry.hf_split, "streaming": True, "token": token}
    if entry.hf_config:
        load_kwargs["name"] = entry.hf_config
    try:
        dataset = load_dataset(entry.hf_dataset_id, **load_kwargs)
        example = next(iter(dataset))
    except Exception as exc:  # noqa: BLE001 - probing many third-party datasets, keep going on failure
        print(f"{entry.id}: ERROR loading {entry.hf_dataset_id!r} config={entry.hf_config!r}: {exc}")
        return

    print(f"{entry.id}: dataset={entry.hf_dataset_id} config={entry.hf_config} split={entry.hf_split}")
    print(f"  columns={list(example.keys())}")
    print(f"  guessed audio_column={entry.audio_column!r} text_column={entry.text_column!r}")
    if entry.notes:
        print(f"  notes={entry.notes}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build faso-speech-plus locally by concatenating faso-speech with external sources."
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print feature/column info for every manifest entry and exit, without building anything.",
    )
    parser.add_argument(
        "--config",
        action="append",
        help="Only build this target_config. May be repeated. Default: all verified configs.",
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Also build manifest entries with verified=False (their column mapping may be wrong).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap rows per source, for a fast dry run.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/hf-plus"),
        help="Directory to write <config>/{train,validation}.parquet under. Default: data/hf-plus.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for train/validation split. Default: 42.")
    parser.add_argument(
        "--eval-size",
        type=float,
        default=0.1,
        help="Fraction kept for validation. Default: 0.1.",
    )
    parser.add_argument(
        "--eval-split-name",
        default="validation",
        help="Name for the held-out split. Default: validation.",
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable containing the Hugging Face token. Default: HF_TOKEN.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get(args.token_env) or None

    if args.inspect:
        for entry in MANIFEST:
            inspect_source(entry, token=token)
        return

    selected_configs = set(args.config or [])
    entries = [entry for entry in MANIFEST if entry.verified or args.include_unverified]
    if selected_configs:
        entries = [entry for entry in entries if entry.target_config in selected_configs]
    if not entries:
        raise SystemExit("No manifest entries selected. Check --config and verified flags on MANIFEST.")

    train_by_config: dict[str, list[Dataset]] = defaultdict(list)
    validation_by_config: dict[str, list[Dataset]] = defaultdict(list)
    for entry in entries:
        if not entry.hf_dataset_id:
            print(f"{entry.id}: skipping, no hf_dataset_id configured")
            continue
        print(f"{entry.id}: loading {entry.hf_dataset_id} ...")
        split_names = get_dataset_split_names(
            entry.hf_dataset_id,
            config_name=entry.hf_config,
            token=token,
        )
        train = normalize_source(
            entry,
            split=entry.hf_split,
            limit=args.limit,
            token=token,
        )
        eval_splits = entry.eval_splits
        if not eval_splits and "validation" in split_names:
            eval_splits = ("validation",)

        if eval_splits:
            missing_splits = sorted(set(eval_splits) - set(split_names))
            if missing_splits:
                raise SystemExit(
                    f"{entry.id}: configured evaluation splits do not exist: {missing_splits}; "
                    f"available splits: {split_names}"
                )
            validation = concatenate_splits(
                [
                    normalize_source(
                        entry,
                        split=split,
                        limit=args.limit,
                        token=token,
                    )
                    for split in eval_splits
                ]
            )
        else:
            generated = split_dataset(
                train,
                eval_size=args.eval_size,
                eval_split_name="validation",
                seed=args.seed,
            )
            train = generated["train"]
            validation = generated.get("validation")

        train_by_config[entry.target_config].append(train)
        if validation is not None:
            validation_by_config[entry.target_config].append(validation)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for config_name, train_datasets in sorted(train_by_config.items()):
        train = concatenate_splits(train_datasets)
        validation_datasets = validation_by_config.get(config_name, [])
        if not validation_datasets:
            raise SystemExit(f"No validation rows available for config {config_name!r}")
        validation = concatenate_splits(validation_datasets)
        train, validation = dedup_train_validation(
            train,
            validation,
            text_only=config_name == "bambara_jula",
        )
        combined = concatenate_datasets([train, validation])
        print_summary(config_name, combined)

        splits = {"train": train, args.eval_split_name: validation}
        config_dir = args.output_dir / config_name
        config_dir.mkdir(parents=True, exist_ok=True)
        for split_name, split_ds in splits.items():
            parquet_path = config_dir / f"{split_name}.parquet"
            split_ds.to_parquet(str(parquet_path))
            print(f"  wrote {parquet_path} rows={len(split_ds)}")


if __name__ == "__main__":
    main()
