from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from faso_speech.archive import archive_entries
from faso_speech.catalog import list_entries
from faso_speech.extraction import extract_timed
from faso_speech.processing.segment_processed import segment_processed_tree
from faso_speech.processing.segment_dataset import prepare_segmented_dataset
from faso_speech.review_ui import run_review_ui
from faso_speech.status import summarize_index

app = typer.Typer(help="Build reproducible Burkina Faso speech datasets.")
catalog_app = typer.Typer(help="Inspect source catalog entries.")
extract_app = typer.Typer(help="Extract candidate chunks from archived data.")
preprocess_app = typer.Typer(help="Prepare chunks and metadata for training/upload.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(extract_app, name="extract")
app.add_typer(preprocess_app, name="preprocess")


@catalog_app.command("list")
def catalog_list(
    filter_expr: Annotated[str, typer.Option("--filter")] = "",
) -> None:
    for entry in list_entries(filter_expr=filter_expr):
        typer.echo(
            f"{entry.id}\t{entry.language}\t{entry.content_type}\t"
            f"{entry.source_site}\tpriority={entry.priority}"
        )


@app.command()
def archive(
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/raw_sources"),
    catalog_id: Annotated[str, typer.Option("--catalog-id")] = "",
    filter_expr: Annotated[str, typer.Option("--filter")] = "",
    refresh: bool = False,
    no_audio: Annotated[bool, typer.Option("--no-audio")] = False,
    dry_run: bool = False,
    max_pages: Annotated[int, typer.Option("--max-pages")] = 0,
    save_source_html: bool = False,
) -> None:
    archived, failed = archive_entries(
        output_dir=output_dir,
        catalog_id=catalog_id,
        filter_expr=filter_expr,
        refresh=refresh,
        download_audio=not no_audio,
        dry_run=dry_run,
        max_pages=max_pages,
        save_source_html=save_source_html,
    )
    typer.echo(f"archived={archived} failed={failed}")


@extract_app.command("timed")
def extract_timed_command(
    input_index: Annotated[Path, typer.Option("--input-index")],
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/processed"),
    catalog_id: Annotated[str, typer.Option("--catalog-id")] = "",
    filter_expr: Annotated[str, typer.Option("--filter")] = "",
    audio_format: Annotated[str, typer.Option("--audio-format")] = "wav",
    start_padding: float = 0.0,
    end_padding: float = 0.0,
    dry_run: bool = False,
) -> None:
    count = extract_timed(
        input_index=input_index,
        output_dir=output_dir,
        catalog_id=catalog_id,
        filter_expr=filter_expr,
        audio_format=audio_format,
        start_padding=start_padding,
        end_padding=end_padding,
        dry_run=dry_run,
    )
    typer.echo(f"candidate_chunks={count}")


@extract_app.command("untimed")
def extract_untimed() -> None:
    typer.echo("extract untimed is not implemented yet")


@preprocess_app.command("hf-training")
def preprocess_hf_training(
    audio: Annotated[Path, typer.Option("--audio")],
    text: Annotated[Path, typer.Option("--text")],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    segments: Annotated[Path | None, typer.Option("--segments")] = None,
    language: Annotated[Literal["moore", "fulfulde", "dioula"], typer.Option("--language")] = "moore",
    audio_format: Annotated[str, typer.Option("--audio-format")] = "wav",
    start_padding: float = 0.15,
    end_padding: float = 0.15,
    min_char_per_second: float = 0.0,
    max_char_per_second: float = 0.0,
) -> None:
    count = prepare_segmented_dataset(
        audio_path=audio,
        text_path=text,
        output_dir=output_dir,
        segments_path=segments,
        language=language,
        audio_format=audio_format,
        start_padding=start_padding,
        end_padding=end_padding,
        min_char_per_second=min_char_per_second,
        max_char_per_second=max_char_per_second,
    )
    typer.echo(f"training_rows={count}")
    typer.echo(f"metadata={output_dir / 'metadata.csv'}")


@preprocess_app.command("segments")
def preprocess_segments(
    input_dir: Annotated[Path, typer.Option("--input-dir")] = Path("data/processed"),
    metadata: Annotated[Path | None, typer.Option("--metadata")] = None,
    language: Annotated[list[str] | None, typer.Option("--language")] = None,
    content_type: Annotated[list[str] | None, typer.Option("--content-type")] = None,
    refresh: bool = False,
    dry_run: bool = False,
    limit: int = 0,
    min_duration: float = 0.72,
    log: Annotated[Path | None, typer.Option("--log")] = None,
) -> None:
    count = segment_processed_tree(
        input_dir,
        metadata_path=metadata,
        languages=set(language or []),
        content_types=set(content_type or []),
        refresh=refresh,
        dry_run=dry_run,
        limit=limit,
        min_duration=min_duration,
        log_path=log,
    )
    typer.echo(f"segmentation_jobs={count}")


@app.command()
def discover(
    catalog_id: Annotated[str, typer.Option("--catalog-id")] = "",
    filter_expr: Annotated[str, typer.Option("--filter")] = "",
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/raw_sources"),
    dry_run: bool = False,
) -> None:
    # First implementation keeps discovery inside archive. This command exposes
    # the catalog scope that archive would inspect.
    del output_dir, dry_run
    for entry in list_entries(catalog_id=catalog_id, filter_expr=filter_expr):
        typer.echo(f"{entry.id}\t{entry.source_url}\t{entry.app_url}")


@app.command()
def status(input_index: Annotated[Path, typer.Option("--input-index")]) -> None:
    for row in summarize_index(input_index):
        typer.echo(
            f"{row['catalog_id']}: pages={row['pages_archived']} "
            f"audio={row['audio_found']} timings={row['timings_found']} "
            f"statuses={row['statuses']}"
        )


@app.command()
def review(
    metadata: Annotated[Path, typer.Argument(help="Processed metadata CSV to review.")],
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8050,
    debug: bool = False,
) -> None:
    run_review_ui(metadata, host=host, port=port, debug=debug)
