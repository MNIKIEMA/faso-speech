from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from faso_speech.audio import audio_duration
from faso_speech.io import write_and_rename
from faso_speech.processing.segment import run_inaspeechsegmenter


AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".ogg", ".wav"}
MIN_SEGMENTER_DURATION_SECONDS = 0.72
LOG_COLUMNS = ["status", "audio_path", "output_csv", "duration", "segments", "message"]
SEGMENT_COLUMNS = ["label", "start", "end", "duration"]


@dataclass(frozen=True)
class SegmentationJob:
    audio_path: Path
    output_csv: Path


def filter_values(values: list[str] | None) -> set[str]:
    return {value.strip() for value in values or [] if value.strip()}


def row_matches_filters(
    row: dict[str, str],
    *,
    languages: set[str],
    content_types: set[str],
) -> bool:
    if languages and row.get("language", "").strip() not in languages:
        return False
    if content_types and row.get("content_type", "").strip() not in content_types:
        return False
    return True


def resolve_path(path_text: str, *, base_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute() or path.exists():
        return path
    return base_dir / path


def segment_csv_name(row: dict[str, str], audio_path: Path) -> str:
    chunk_id = row.get("chunk_id", "").strip()
    if chunk_id:
        return f"{chunk_id}.segments.csv"
    if audio_path.stem == "audio" and audio_path.parent.name:
        return f"{audio_path.parent.name}.segments.csv"
    return f"{audio_path.stem}.segments.csv"


def jobs_from_metadata(
    input_dir: Path,
    metadata_path: Path,
    *,
    languages: set[str],
    content_types: set[str],
) -> list[SegmentationJob]:
    jobs_by_audio: dict[Path, SegmentationJob] = {}
    with metadata_path.open(newline="", encoding="utf-8") as input_file:
        for row in csv.DictReader(input_file):
            if not row_matches_filters(row, languages=languages, content_types=content_types):
                continue
            chunk_audio = row.get("chunk_audio", "").strip()
            if not chunk_audio:
                continue
            audio_path = resolve_path(chunk_audio, base_dir=metadata_path.parent)
            if audio_path in jobs_by_audio:
                continue
            language = row.get("language", "").strip() or "unknown_language"
            content_type = row.get("content_type", "").strip() or "unknown_content"
            output_csv = (
                input_dir
                / language
                / content_type
                / "segments"
                / segment_csv_name(row, audio_path)
            )
            jobs_by_audio[audio_path] = SegmentationJob(audio_path=audio_path, output_csv=output_csv)
    return sorted(jobs_by_audio.values(), key=lambda job: str(job.output_csv))


def path_matches_filters(path: Path, *, languages: set[str], content_types: set[str]) -> bool:
    parts = set(path.parts)
    if languages and not parts.intersection(languages):
        return False
    if content_types and not parts.intersection(content_types):
        return False
    return True


def jobs_from_audio_scan(
    input_dir: Path,
    *,
    languages: set[str],
    content_types: set[str],
) -> list[SegmentationJob]:
    jobs = []
    for audio_path in sorted(input_dir.rglob("*")):
        if not audio_path.is_file() or audio_path.suffix.lower() not in AUDIO_SUFFIXES:
            continue
        relative_audio = audio_path.relative_to(input_dir)
        if not path_matches_filters(
            relative_audio,
            languages=languages,
            content_types=content_types,
        ):
            continue
        output_csv = input_dir / "segments" / relative_audio.with_suffix(".segments.csv")
        jobs.append(SegmentationJob(audio_path=audio_path, output_csv=output_csv))
    return jobs


def discover_segmentation_jobs(
    input_dir: Path,
    *,
    metadata_path: Path | None = None,
    languages: set[str] | None = None,
    content_types: set[str] | None = None,
) -> list[SegmentationJob]:
    languages = languages or set()
    content_types = content_types or set()
    metadata_path = metadata_path or input_dir / "metadata.csv"
    if metadata_path.exists():
        return jobs_from_metadata(
            input_dir,
            metadata_path,
            languages=languages,
            content_types=content_types,
        )
    return jobs_from_audio_scan(input_dir, languages=languages, content_types=content_types)


def safe_audio_duration(audio_path: Path) -> float | None:
    try:
        return audio_duration(audio_path)
    except ValueError:
        return None


def write_log(path: Path, rows: list[dict[str, object]]) -> None:
    with write_and_rename(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_segments_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    with write_and_rename(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=SEGMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def log_row(
    rows: list[dict[str, object]],
    *,
    status: str,
    job: SegmentationJob,
    duration: float | None = None,
    segments: int | str = "",
    message: str = "",
) -> None:
    rows.append(
        {
            "status": status,
            "audio_path": str(job.audio_path),
            "output_csv": str(job.output_csv),
            "duration": "" if duration is None else round(duration, 3),
            "segments": segments,
            "message": message,
        }
    )


def segment_processed_tree(
    input_dir: Path,
    *,
    metadata_path: Path | None = None,
    languages: set[str] | None = None,
    content_types: set[str] | None = None,
    refresh: bool = False,
    dry_run: bool = False,
    limit: int = 0,
    min_duration: float = MIN_SEGMENTER_DURATION_SECONDS,
    log_path: Path | None = None,
) -> int:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    jobs = discover_segmentation_jobs(
        input_dir,
        metadata_path=metadata_path,
        languages=languages,
        content_types=content_types,
    )
    processed = 0
    log_rows: list[dict[str, object]] = []
    log_path = log_path or input_dir / "segmentation_log.csv"
    try:
        for job in jobs:
            if limit and processed >= limit:
                break
            if not job.audio_path.exists():
                print(f"missing_audio\t{job.audio_path}")
                log_row(log_rows, status="missing_audio", job=job)
                continue
            if job.output_csv.exists() and not refresh:
                print(f"skip_existing\t{job.output_csv}")
                log_row(log_rows, status="skip_existing", job=job)
                continue
            duration = safe_audio_duration(job.audio_path)
            if duration is None:
                print(f"skip_unknown_duration\t{job.audio_path}")
                log_row(log_rows, status="skip_unknown_duration", job=job)
                continue
            if duration < min_duration:
                print(f"skip_short\t{job.audio_path}\tduration={duration:.3f}")
                log_row(log_rows, status="skip_short", job=job, duration=duration)
                continue
            if dry_run:
                print(f"would_segment\t{job.audio_path}\t{job.output_csv}")
                log_row(log_rows, status="would_segment", job=job, duration=duration)
                processed += 1
                continue

            rows = run_inaspeechsegmenter(job.audio_path)
            write_segments_csv(job.output_csv, rows)
            print(f"segmented\t{job.audio_path}\t{job.output_csv}\tsegments={len(rows)}")
            log_row(
                log_rows,
                status="segmented",
                job=job,
                duration=duration,
                segments=len(rows),
            )
            processed += 1
    finally:
        write_log(log_path, log_rows)
        print(f"segmentation_log={log_path}")
    return processed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run speech/noise/music segmentation for a processed data tree."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/processed"),
        help="Processed data directory. Default: data/processed.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Optional metadata CSV. Default: <input-dir>/metadata.csv.",
    )
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        help="Only segment this language. Can be repeated, e.g. --language moore --language dioula.",
    )
    parser.add_argument(
        "--content-type",
        action="append",
        dest="content_types",
        help="Only segment this content type. Can be repeated, e.g. --content-type contes.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Recreate segment CSVs that already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the segmentation jobs without running the segmenter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of jobs to process. Default: no limit.",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=MIN_SEGMENTER_DURATION_SECONDS,
        help="Skip audio shorter than this many seconds. Default: 0.72.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="CSV path for per-audio segmentation outcomes. Default: <input-dir>/segmentation_log.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = segment_processed_tree(
        args.input_dir,
        metadata_path=args.metadata,
        languages=filter_values(args.languages),
        content_types=filter_values(args.content_types),
        refresh=args.refresh,
        dry_run=args.dry_run,
        limit=args.limit,
        min_duration=args.min_duration,
        log_path=args.log,
    )
    print(f"segmentation_jobs={count}")


if __name__ == "__main__":
    main()
