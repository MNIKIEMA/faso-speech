# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pylance>=0.22.0",
# ]
# ///
"""Benchmark Lance vs CSV+filesystem for the moore contes processed chunks.

Reads data/processed/metadata.csv, filters to moore contes rows, embeds the
chunk audio WAV bytes, writes a Lance dataset, then compares a few access
patterns between the CSV+files baseline and the Lance dataset.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import lance
import pyarrow as pa


METADATA_PATH = Path("data/processed/metadata.csv")
CHUNK_AUDIO_DIR = Path("data/processed/moore/contes/timed_chunks/chunks")
DEFAULT_LANCE_URI = Path("tmp/moore_contes.lance")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def filter_moore_contes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("language") == "moore" and row.get("content_type") == "contes"
    ]


def row_audio_path(row: dict[str, str]) -> Path | None:
    chunk_audio = row.get("chunk_audio", "").strip()
    if not chunk_audio:
        return None
    path = Path(chunk_audio)
    if path.is_absolute():
        return path
    return CHUNK_AUDIO_DIR / path.name


def enrich_row_with_audio(row: dict[str, str]) -> dict[str, object] | None:
    audio_path = row_audio_path(row)
    if audio_path is None or not audio_path.is_file():
        return None
    try:
        audio_bytes = audio_path.read_bytes()
    except OSError:
        return None

    def num_or(value: str, default: float) -> float:
        try:
            return float(value)
        except ValueError:
            return default

    return {
        "chunk_id": row.get("chunk_id", ""),
        "record_id": row.get("record_id", ""),
        "catalog_id": row.get("catalog_id", ""),
        "language": row.get("language", ""),
        "content_type": row.get("content_type", ""),
        "source_site": row.get("source_site", ""),
        "source_url": row.get("source_url", ""),
        "app_url": row.get("app_url", ""),
        "source_audio": row.get("source_audio", ""),
        "audio_url": row.get("audio_url", ""),
        "label": row.get("label", ""),
        "unit_type": row.get("unit_type", ""),
        "book": row.get("book", ""),
        "chapter": row.get("chapter", ""),
        "verse": row.get("verse", ""),
        "start": num_or(row.get("start", ""), 0.0),
        "end": num_or(row.get("end", ""), 0.0),
        "duration": num_or(row.get("duration", ""), 0.0),
        "text": row.get("text", ""),
        "status": row.get("status", ""),
        "review_note": row.get("review_note", ""),
        "created_at": row.get("created_at", ""),
        "audio_bytes": audio_bytes,
    }


def build_arrow_table(rows: list[dict[str, str]]) -> pa.Table:
    enriched = []
    missing_audio = 0
    for row in rows:
        out = enrich_row_with_audio(row)
        if out is None:
            missing_audio += 1
            continue
        enriched.append(out)
    if missing_audio:
        print(f"warning: skipped {missing_audio} rows with missing audio")

    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("record_id", pa.string()),
            ("catalog_id", pa.string()),
            ("language", pa.string()),
            ("content_type", pa.string()),
            ("source_site", pa.string()),
            ("source_url", pa.string()),
            ("app_url", pa.string()),
            ("source_audio", pa.string()),
            ("audio_url", pa.string()),
            ("label", pa.string()),
            ("unit_type", pa.string()),
            ("book", pa.string()),
            ("chapter", pa.string()),
            ("verse", pa.string()),
            ("start", pa.float64()),
            ("end", pa.float64()),
            ("duration", pa.float64()),
            ("text", pa.string()),
            ("status", pa.string()),
            ("review_note", pa.string()),
            ("created_at", pa.string()),
            ("audio_bytes", pa.binary()),
        ]
    )
    arrays = [
        pa.array([row[name] for row in enriched], type=field.type)
        for name, field in zip(schema.names, schema)
    ]
    return pa.Table.from_arrays(arrays, names=schema.names)


def write_lance(table: pa.Table, uri: Path, overwrite: bool = True) -> Path:
    uri.mkdir(parents=True, exist_ok=True)
    if overwrite and any(uri.iterdir()):
        for child in uri.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                import shutil

                shutil.rmtree(child)
    lance.write_dataset(table, str(uri), mode="overwrite")
    return uri


def timeit(label: str, fn, rounds: int = 1):
    durations = []
    for _ in range(rounds):
        start = time.perf_counter()
        result = fn()
        durations.append(time.perf_counter() - start)
    avg = sum(durations) / len(durations)
    print(f"{label}: {avg:.4f}s (best {min(durations):.4f}s, rounds={rounds})")
    return result


def csv_full_scan(rows: list[dict[str, str]]) -> tuple[int, int]:
    total_bytes = 0
    count = 0
    for row in rows:
        audio_path = row_audio_path(row)
        if audio_path and audio_path.is_file():
            total_bytes += len(audio_path.read_bytes())
            count += 1
    return count, total_bytes


def csv_filter_short(rows: list[dict[str, str]], max_duration: float) -> tuple[int, int]:
    total_bytes = 0
    count = 0
    for row in rows:
        try:
            duration = float(row.get("duration", "0"))
        except ValueError:
            continue
        if duration > max_duration:
            continue
        audio_path = row_audio_path(row)
        if audio_path and audio_path.is_file():
            total_bytes += len(audio_path.read_bytes())
            count += 1
    return count, total_bytes


def csv_random_sample(rows: list[dict[str, str]], n: int, seed: int) -> tuple[int, int]:
    sampled = random.Random(seed).sample(rows, min(n, len(rows)))
    total_bytes = 0
    count = 0
    for row in sampled:
        audio_path = row_audio_path(row)
        if audio_path and audio_path.is_file():
            total_bytes += len(audio_path.read_bytes())
            count += 1
    return count, total_bytes


def lance_full_scan(ds: lance.LanceDataset) -> tuple[int, int]:
    table = ds.to_table(columns=["audio_bytes"])
    blobs = table["audio_bytes"].to_pylist()
    return len(blobs), sum(len(b) for b in blobs)


def lance_filter_short(ds: lance.LanceDataset, max_duration: float) -> tuple[int, int]:
    table = ds.to_table(columns=["audio_bytes"], filter=f"duration <= {max_duration}")
    blobs = table["audio_bytes"].to_pylist()
    return len(blobs), sum(len(b) for b in blobs)


def lance_random_sample(ds: lance.LanceDataset, n: int, seed: int) -> tuple[int, int]:
    total = ds.count_rows()
    indices = random.Random(seed).sample(range(total), min(n, total))
    table = ds.take(indices, columns=["audio_bytes"])
    blobs = table["audio_bytes"].to_pylist()
    return len(blobs), sum(len(b) for b in blobs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Lance vs CSV+filesystem for moore contes chunks."
    )
    parser.add_argument(
        "--lance-uri",
        type=Path,
        default=DEFAULT_LANCE_URI,
        help="Where to write the Lance dataset. Default: tmp/moore_contes.lance",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=5.0,
        help="Duration threshold (seconds) for the filter benchmark. Default: 5.0",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=500,
        help="Number of rows for the random sample benchmark. Default: 500",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Benchmark rounds per operation. Default: 3",
    )
    args = parser.parse_args()

    print("Reading metadata CSV...")
    all_rows = read_csv_rows(METADATA_PATH)
    moore_contes_rows = filter_moore_contes(all_rows)
    print(f"Total rows: {len(all_rows)}, moore contes rows: {len(moore_contes_rows)}")

    print("\nBuilding Arrow table with embedded audio bytes...")
    table = build_arrow_table(moore_contes_rows)
    print(f"Arrow table rows: {table.num_rows}")
    print(f"Arrow table size: {table.nbytes / 1024 / 1024:.2f} MB")

    print(f"\nWriting Lance dataset to {args.lance_uri}...")
    write_lance(table, args.lance_uri)
    ds = lance.dataset(str(args.lance_uri))
    print(f"Lance dataset rows: {ds.count_rows()}")

    print("\n--- Benchmarks ---")
    print(f"Operation: read audio bytes for all rows (rounds={args.rounds})")
    csv_count, csv_bytes = timeit(
        "CSV+fs full scan", lambda: csv_full_scan(moore_contes_rows), rounds=args.rounds
    )
    lance_count, lance_bytes = timeit(
        "Lance full scan", lambda: lance_full_scan(ds), rounds=args.rounds
    )
    print(f"  CSV rows={csv_count}, bytes={csv_bytes / 1024 / 1024:.2f} MB")
    print(f"  Lance rows={lance_count}, bytes={lance_bytes / 1024 / 1024:.2f} MB")

    print(f"\nOperation: filter duration <= {args.max_duration}s (rounds={args.rounds})")
    csv_count, csv_bytes = timeit(
        "CSV+fs filter",
        lambda: csv_filter_short(moore_contes_rows, args.max_duration),
        rounds=args.rounds,
    )
    lance_count, lance_bytes = timeit(
        "Lance filter",
        lambda: lance_filter_short(ds, args.max_duration),
        rounds=args.rounds,
    )
    print(f"  CSV rows={csv_count}, bytes={csv_bytes / 1024 / 1024:.2f} MB")
    print(f"  Lance rows={lance_count}, bytes={lance_bytes / 1024 / 1024:.2f} MB")

    print(f"\nOperation: random sample of {args.sample_n} rows (rounds={args.rounds})")
    csv_count, csv_bytes = timeit(
        "CSV+fs sample",
        lambda: csv_random_sample(moore_contes_rows, args.sample_n, seed=42),
        rounds=args.rounds,
    )
    lance_count, lance_bytes = timeit(
        "Lance sample",
        lambda: lance_random_sample(ds, args.sample_n, seed=42),
        rounds=args.rounds,
    )
    print(f"  CSV rows={csv_count}, bytes={csv_bytes / 1024 / 1024:.2f} MB")
    print(f"  Lance rows={lance_count}, bytes={lance_bytes / 1024 / 1024:.2f} MB")

    print(
        f"\nOperation: metadata-only filter duration <= {args.max_duration}s (rounds={args.rounds})"
    )

    def csv_metadata_filter() -> int:
        return sum(
            1 for row in moore_contes_rows if float(row.get("duration") or 0) <= args.max_duration
        )

    def lance_metadata_filter() -> int:
        return ds.count_rows(filter=f"duration <= {args.max_duration}")

    csv_meta_count = timeit("CSV+fs metadata filter", csv_metadata_filter, rounds=args.rounds)
    lance_meta_count = timeit("Lance metadata filter", lance_metadata_filter, rounds=args.rounds)
    print(f"  CSV matching rows={csv_meta_count}")
    print(f"  Lance matching rows={lance_meta_count}")

    print("\n--- Storage size ---")
    csv_audio_bytes = sum(
        Path(row["chunk_audio"]).stat().st_size
        for row in moore_contes_rows
        if row.get("chunk_audio") and Path(row["chunk_audio"]).is_file()
    )
    lance_size = sum(f.stat().st_size for f in args.lance_uri.rglob("*") if f.is_file())
    print(f"CSV audio files total: {csv_audio_bytes / 1024 / 1024:.2f} MB")
    print(f"Lance dataset total:   {lance_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
