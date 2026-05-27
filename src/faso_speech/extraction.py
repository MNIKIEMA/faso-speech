from __future__ import annotations

import csv
from pathlib import Path

from faso_speech.audio import cut_audio
from faso_speech.models import RecordStatus


METADATA_COLUMNS = [
    "chunk_id",
    "record_id",
    "catalog_id",
    "language",
    "content_type",
    "source_site",
    "source_url",
    "app_url",
    "source_audio",
    "audio_url",
    "label",
    "unit_type",
    "book",
    "chapter",
    "verse",
    "start",
    "end",
    "duration",
    "chunk_audio",
    "chunk_text",
    "text",
    "status",
    "review_note",
    "created_at",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as input_file:
        return list(csv.DictReader(input_file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text}\n", encoding="utf-8")


def parse_filter(filter_expr: str) -> dict[str, str]:
    if not filter_expr:
        return {}
    filters = {}
    for item in filter_expr.split():
        key, separator, value = item.partition("=")
        if not separator:
            raise ValueError(f"invalid filter item: {item!r}")
        filters[key] = value
    return filters


def extract_timed(
    *,
    input_index: Path,
    output_dir: Path,
    catalog_id: str = "",
    filter_expr: str = "",
    audio_format: str = "wav",
    start_padding: float = 0.0,
    end_padding: float = 0.0,
    dry_run: bool = False,
) -> int:
    index_rows = read_csv(input_index)
    filters = parse_filter(filter_expr)
    chunk_rows: list[dict[str, object]] = []

    for record in index_rows:
        if catalog_id and record["catalog_id"] != catalog_id:
            continue
        if any(record.get(key, "") != value for key, value in filters.items()):
            continue
        if record.get("status") != RecordStatus.ARCHIVED.value:
            continue
        if not record.get("audio_path"):
            continue

        timings = read_csv(Path(record["timings_path"]))
        text_blocks = {row["label"]: row for row in read_csv(Path(record["text_path"]))}
        base_dir = output_dir / record["language"] / record["content_type"] / "timed_chunks"
        chunk_dir = base_dir / "chunks"

        for index, timing in enumerate(timings, start=1):
            text_row = text_blocks.get(timing["label"])
            if not text_row or not text_row.get("text"):
                continue

            chunk_id = f"{record['record_id']}_{index:03d}_{timing['label']}"
            chunk_audio = chunk_dir / f"{chunk_id}.{audio_format}"
            chunk_text = chunk_dir / f"{chunk_id}.txt"
            start = float(timing["start"])
            end = float(timing["end"])

            if not dry_run:
                cut_audio(
                    Path(record["audio_path"]),
                    chunk_audio,
                    start=start,
                    end=end,
                    audio_format=audio_format,
                    start_padding=start_padding,
                    end_padding=end_padding,
                )
                write_text(chunk_text, text_row["text"])

            chunk_rows.append(
                {
                    "chunk_id": chunk_id,
                    "record_id": record["record_id"],
                    "catalog_id": record["catalog_id"],
                    "language": text_row.get("language") or record["language"],
                    "content_type": record["content_type"],
                    "source_site": record["source_site"],
                    "source_url": record["source_url"],
                    "app_url": record["app_url"],
                    "source_audio": record["audio_path"],
                    "audio_url": record["audio_url"],
                    "label": timing["label"],
                    "unit_type": "timed_text_block",
                    "book": "",
                    "chapter": "",
                    "verse": "",
                    "start": start,
                    "end": end,
                    "duration": round(end - start, 3),
                    "chunk_audio": str(chunk_audio),
                    "chunk_text": str(chunk_text),
                    "text": text_row["text"],
                    "status": RecordStatus.CANDIDATE.value,
                    "review_note": "",
                    "created_at": record["scraped_at"],
                }
            )

    if not dry_run:
        write_csv(output_dir / "metadata.csv", chunk_rows, METADATA_COLUMNS)
    return len(chunk_rows)
