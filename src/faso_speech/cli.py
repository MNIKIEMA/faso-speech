from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from faso_speech.archive import archive_entries
from faso_speech.catalog import list_entries
from faso_speech.extraction import extract_timed
from faso_speech.status import summarize_index


app = typer.Typer(help="Build reproducible Burkina Faso speech datasets.")
catalog_app = typer.Typer(help="Inspect source catalog entries.")
extract_app = typer.Typer(help="Extract candidate chunks from archived data.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(extract_app, name="extract")


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
