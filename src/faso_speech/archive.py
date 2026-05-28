from __future__ import annotations

import csv
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import msgspec

from faso_speech.catalog import list_entries
from faso_speech.http import download_file, fetch_text
from faso_speech.models import (
    ArchiveRecord,
    CatalogEntry,
    ParsedPage,
    RecordStatus,
    SourceRecord,
    TextBlock,
    Timing,
)
from faso_speech.parsers.app_builder import parse_page
from faso_speech.sources.mooreburkina import app_name, discover_record, page_stem


INDEX_COLUMNS = [
    "record_id",
    "catalog_id",
    "language",
    "content_type",
    "source_site",
    "source_url",
    "app_url",
    "parser",
    "title",
    "audio_url",
    "audio_path",
    "source_html_path",
    "app_html_path",
    "text_path",
    "timings_path",
    "markers_path",
    "has_audio",
    "has_timing",
    "has_markers",
    "status",
    "warnings",
    "scraped_at",
    "license",
    "attribution",
]

FAILURE_COLUMNS = [
    "timestamp",
    "phase",
    "record_id",
    "catalog_id",
    "url",
    "language",
    "content_type",
    "source_site",
    "error_type",
    "error_message",
    "retry_count",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_existing_record_ids(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    with index_path.open(newline="", encoding="utf-8") as input_file:
        return {row["record_id"] for row in csv.DictReader(input_file)}


def write_metadata(path: Path, record: ArchiveRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msgspec.json.encode(record))
    with path.open("ab") as output_file:
        output_file.write(b"\n")


def write_text_blocks(path: Path, blocks: list[TextBlock]) -> None:
    write_csv(
        path,
        [
            {"label": block.label, "language": block.language, "text": block.text}
            for block in blocks
        ],
        ["label", "language", "text"],
    )


def write_timings(path: Path, timings: list[Timing]) -> None:
    write_csv(
        path,
        [
            {
                "label": timing.label,
                "start": timing.start,
                "end": timing.end,
                "duration": timing.duration,
            }
            for timing in timings
        ],
        ["label", "start", "end", "duration"],
    )


def archive_status(parsed: ParsedPage) -> RecordStatus:
    if not parsed.audio_url:
        return RecordStatus.MISSING_AUDIO
    if not parsed.text_blocks:
        return RecordStatus.MISSING_TEXT
    if not parsed.timings:
        return RecordStatus.MISSING_TIMING
    return RecordStatus.ARCHIVED


def record_id_for(record: SourceRecord) -> str:
    return f"{record.catalog_id}-{page_stem(record.app_url)}"


def archive_record_dir(output_dir: Path, record: SourceRecord) -> Path:
    return (
        output_dir
        / record.language
        / record.content_type
        / app_name(record.app_url)
        / page_stem(record.app_url)
    )


def archive_one_page(
    record: SourceRecord,
    app_html: str,
    output_dir: Path,
    *,
    download_audio: bool,
    source_html: str = "",
) -> ArchiveRecord:
    parsed = parse_page(app_html, record)
    page_dir = archive_record_dir(output_dir, record)
    page_dir.mkdir(parents=True, exist_ok=True)

    app_html_path = page_dir / "app.html"
    app_html_path.write_text(app_html, encoding="utf-8")

    source_html_path = ""
    if source_html:
        source_path = page_dir.parent / "source.html"
        source_path.write_text(source_html, encoding="utf-8")
        source_html_path = str(source_path)

    audio_path = ""
    if download_audio and parsed.audio_url:
        suffix = Path(urllib.parse.urlsplit(parsed.audio_url).path).suffix or ".mp3"
        audio_file = page_dir / f"audio{suffix}"
        if not audio_file.exists():
            download_file(parsed.audio_url, audio_file)
        audio_path = str(audio_file)

    timings_path = page_dir / "timings.csv"
    text_path = page_dir / "text.csv"
    write_timings(timings_path, parsed.timings)
    write_text_blocks(text_path, parsed.text_blocks)

    archive_record = ArchiveRecord(
        record_id=record_id_for(record),
        catalog_id=record.catalog_id,
        language=record.language,
        content_type=record.content_type,
        source_site=record.source_site,
        source_url=record.source_url,
        app_url=record.app_url,
        parser=record.parser,
        title=parsed.title,
        audio_url=parsed.audio_url,
        audio_path=audio_path,
        source_html_path=source_html_path,
        app_html_path=str(app_html_path),
        text_path=str(text_path),
        timings_path=str(timings_path),
        markers_path="",
        has_audio=bool(parsed.audio_url),
        has_timing=bool(parsed.timings),
        has_markers=False,
        status=archive_status(parsed),
        warnings=parsed.warnings,
        scraped_at=utc_now(),
        license=record.license,
        attribution=record.attribution,
    )
    write_metadata(page_dir / "metadata.json", archive_record)
    return archive_record


def archive_to_index_row(record: ArchiveRecord) -> dict[str, object]:
    data = msgspec.to_builtins(record)
    data["status"] = record.status.value
    data["warnings"] = json.dumps(record.warnings, ensure_ascii=False)
    return {column: data.get(column, "") for column in INDEX_COLUMNS}


def failure_row(
    *,
    phase: str,
    entry: CatalogEntry,
    url: str,
    error: Exception,
    record_id: str = "",
) -> dict[str, object]:
    return {
        "timestamp": utc_now(),
        "phase": phase,
        "record_id": record_id,
        "catalog_id": entry.id,
        "url": url,
        "language": entry.language,
        "content_type": entry.content_type,
        "source_site": entry.source_site,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "retry_count": 0,
    }


def archive_entries(
    *,
    output_dir: Path,
    catalog_id: str = "",
    filter_expr: str = "",
    refresh: bool = False,
    download_audio: bool = True,
    dry_run: bool = False,
    max_pages: int = 0,
    save_source_html: bool = False,
) -> tuple[int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.csv"
    failures_path = output_dir / "failures.csv"
    if refresh and not dry_run:
        index_path.unlink(missing_ok=True)
        failures_path.unlink(missing_ok=True)
    existing_ids = set() if refresh else read_existing_record_ids(index_path)

    archived = 0
    failed = 0
    for entry in list_entries(catalog_id=catalog_id, filter_expr=filter_expr):
        if entry.parser != "app_builder" or entry.source_site != "mooreburkina.com":
            continue
        try:
            source_record, app_html, source_html = discover_record(
                entry,
                save_source_html=save_source_html,
            )
        except Exception as error:
            append_csv(
                failures_path,
                [failure_row(phase="discover", entry=entry, url=entry.source_url, error=error)],
                FAILURE_COLUMNS,
            )
            failed += 1
            continue

        page_count = 0
        seen: set[str] = set()
        while source_record.app_url and source_record.app_url not in seen:
            seen.add(source_record.app_url)
            page_count += 1
            if max_pages and page_count > max_pages:
                break
            record_id = record_id_for(source_record)

            try:
                parsed = parse_page(app_html, source_record)
                if dry_run:
                    if record_id not in existing_ids:
                        print(f"would archive {source_record.app_url}")
                elif record_id not in existing_ids:
                    archived_record = archive_one_page(
                        source_record,
                        app_html,
                        output_dir,
                        download_audio=download_audio,
                        source_html=source_html if page_count == 1 else "",
                    )
                    append_csv(index_path, [archive_to_index_row(archived_record)], INDEX_COLUMNS)
                    existing_ids.add(record_id)
                    archived += 1

                if not parsed.next_page:
                    break
                source_record = SourceRecord(
                    catalog_id=source_record.catalog_id,
                    source_url=source_record.source_url,
                    source_site=source_record.source_site,
                    language=source_record.language,
                    content_type=source_record.content_type,
                    app_url=parsed.next_page,
                    audio_url=source_record.audio_url,
                    parser=source_record.parser,
                    license=source_record.license,
                    attribution=source_record.attribution,
                )
                app_html = fetch_text(parsed.next_page)
                source_html = ""
            except Exception as error:
                append_csv(
                    failures_path,
                    [
                        failure_row(
                            phase="archive",
                            entry=entry,
                            url=source_record.app_url,
                            error=error,
                            record_id=record_id,
                        )
                    ],
                    FAILURE_COLUMNS,
                )
                failed += 1
                break

    return archived, failed
