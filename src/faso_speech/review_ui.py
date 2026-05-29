from __future__ import annotations

import base64
import csv
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import abort, send_file

from faso_speech.models import RecordStatus


REVIEW_COLUMNS = [
    "chunk_id",
    "language",
    "content_type",
    "catalog_id",
    "record_id",
    "duration",
    "status",
    "review_note",
    "text",
]
STATUS_OPTIONS = [
    RecordStatus.CANDIDATE.value,
    RecordStatus.ACCEPTED.value,
    RecordStatus.REJECTED.value,
    RecordStatus.NEEDS_REVIEW.value,
    RecordStatus.TIMING_MISMATCH.value,
]
APP_STYLE = """
body {
    margin: 0;
    background: #f6f7f9;
    color: #1f2937;
    font-family: system-ui, sans-serif;
}
.topbar {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    padding: 18px 24px;
    background: #ffffff;
    border-bottom: 1px solid #d8dee8;
}
h1 { margin: 0; font-size: 22px; }
h2 { margin: 0 0 12px; font-size: 18px; }
h3 { margin: 18px 0 8px; font-size: 14px; }
p { margin: 4px 0 0; }
button {
    border: 1px solid #1f2937;
    background: #1f2937;
    color: white;
    border-radius: 6px;
    padding: 9px 14px;
    cursor: pointer;
}
button:hover { background: #111827; }
.filters {
    display: grid;
    grid-template-columns: 180px 180px 200px minmax(280px, 1fr);
    gap: 10px;
    padding: 14px 24px;
    background: #ffffff;
    border-bottom: 1px solid #d8dee8;
}
.stats {
    display: grid;
    grid-template-columns: 150px 150px minmax(220px, 1fr) minmax(220px, 1fr);
    gap: 10px;
    padding: 14px 24px;
}
.stat {
    background: #ffffff;
    border: 1px solid #d8dee8;
    border-radius: 8px;
    padding: 10px 12px;
    min-height: 54px;
}
.stat span { display: block; font-size: 12px; color: #64748b; }
.stat strong { display: block; margin-top: 4px; font-size: 16px; }
.wide strong { font-size: 13px; line-height: 1.35; }
.workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 390px;
    gap: 14px;
    padding: 0 24px 24px;
}
.table-panel,
.detail-panel {
    background: #ffffff;
    border: 1px solid #d8dee8;
    border-radius: 8px;
    overflow: hidden;
}
.detail-panel {
    padding: 16px;
    position: sticky;
    top: 12px;
    align-self: start;
}
audio { width: 100%; margin-bottom: 14px; }
label {
    display: block;
    margin: 12px 0 6px;
    font-size: 12px;
    font-weight: 700;
    color: #475569;
}
textarea {
    width: 100%;
    min-height: 96px;
    resize: vertical;
    font: inherit;
    box-sizing: border-box;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px;
}
input[type="search"] {
    min-height: 38px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0 10px;
    font: inherit;
}
.meta {
    font-size: 12px;
    color: #475569;
    display: grid;
    gap: 4px;
    margin-bottom: 10px;
}
.utterance { white-space: pre-wrap; line-height: 1.5; font-size: 15px; }
.save-message {
    min-height: 22px;
    margin-top: 10px;
    font-size: 13px;
    color: #0f766e;
}
@media (max-width: 1050px) {
    .filters,
    .stats,
    .workspace { grid-template-columns: 1fr; }
    .detail-panel { position: static; }
}
"""


def read_metadata(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        return list(reader), list(reader.fieldnames or [])


def write_metadata(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def option_values(rows: list[dict[str, str]], field: str) -> list[dict[str, str]]:
    values = sorted({row.get(field, "") for row in rows if row.get(field, "")})
    return [{"label": value, "value": value} for value in values]


def row_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["chunk_id"]: row for row in rows if row.get("chunk_id")}


def resolve_audio_path(metadata_path: Path, audio_path: str) -> Path:
    path = Path(audio_path)
    if path.is_absolute():
        return path
    repo_relative = Path.cwd() / path
    if repo_relative.exists():
        return repo_relative
    return metadata_path.parent / path


def media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".ogg":
        return "audio/ogg"
    if suffix == ".flac":
        return "audio/flac"
    return "audio/wav"


def data_uri_for_audio(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type(path)};base64,{payload}"


def filter_rows(
    rows: list[dict[str, str]],
    *,
    language: str,
    content_type: str,
    status: str,
    query: str,
) -> list[dict[str, str]]:
    normalized_query = query.casefold().strip()
    filtered = []
    for row in rows:
        if language and row.get("language") != language:
            continue
        if content_type and row.get("content_type") != content_type:
            continue
        if status and row.get("status") != status:
            continue
        if normalized_query:
            haystack = " ".join(
                [
                    row.get("chunk_id", ""),
                    row.get("record_id", ""),
                    row.get("catalog_id", ""),
                    row.get("text", ""),
                    row.get("review_note", ""),
                ]
            ).casefold()
            if normalized_query not in haystack:
                continue
        filtered.append(row)
    return filtered


def table_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row.get(column, "") for column in REVIEW_COLUMNS} for row in rows]


def summary_cards(rows: list[dict[str, str]], filtered: list[dict[str, str]]) -> list[html.Div]:
    duration = sum(float(row.get("duration") or 0.0) for row in filtered)
    status_counts = Counter(row.get("status", "") for row in filtered)
    language_counts = Counter(row.get("language", "") for row in filtered)
    status_summary = ", ".join(f"{k}:{v}" for k, v in status_counts.items()) or "-"
    language_summary = ", ".join(f"{k}:{v}" for k, v in language_counts.items()) or "-"
    return [
        html.Div(
            [html.Span("Rows"), html.Strong(f"{len(filtered):,} / {len(rows):,}")],
            className="stat",
        ),
        html.Div(
            [html.Span("Hours"), html.Strong(f"{duration / 3600:.2f}")],
            className="stat",
        ),
        html.Div(
            [html.Span("Statuses"), html.Strong(status_summary)],
            className="stat wide",
        ),
        html.Div(
            [html.Span("Languages"), html.Strong(language_summary)],
            className="stat wide",
        ),
    ]


def build_app(metadata_path: Path) -> Dash:
    metadata_path = metadata_path.resolve()
    rows, fieldnames = read_metadata(metadata_path)
    rows_by_id = row_lookup(rows)
    audio_paths = {
        chunk_id: resolve_audio_path(metadata_path, row.get("chunk_audio", ""))
        for chunk_id, row in rows_by_id.items()
    }

    app = Dash(__name__)
    app.title = "Faso Speech Review"
    app.index_string = f"""
    <!DOCTYPE html>
    <html>
        <head>
            {{%metas%}}
            <title>{{%title%}}</title>
            {{%favicon%}}
            {{%css%}}
            <style>{APP_STYLE}</style>
        </head>
        <body>
            {{%app_entry%}}
            <footer>
                {{%config%}}
                {{%scripts%}}
                {{%renderer%}}
            </footer>
        </body>
    </html>
    """

    @app.server.route("/review-audio/<chunk_id>")
    def serve_audio(chunk_id: str):
        path = audio_paths.get(chunk_id)
        if not path or not path.exists():
            abort(404)
        return send_file(path, mimetype=media_type(path), conditional=True)

    app.layout = html.Div(
        [
            dcc.Store(id="selected-chunk-id"),
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("Faso Speech Review"),
                            html.P(str(metadata_path)),
                        ]
                    ),
                    html.Button("Save", id="save-button", n_clicks=0),
                ],
                className="topbar",
            ),
            html.Section(
                [
                    dcc.Dropdown(
                        id="language-filter",
                        options=option_values(rows, "language"),
                        placeholder="Language",
                        clearable=True,
                    ),
                    dcc.Dropdown(
                        id="content-filter",
                        options=option_values(rows, "content_type"),
                        placeholder="Content",
                        clearable=True,
                    ),
                    dcc.Dropdown(
                        id="status-filter",
                        options=option_values(rows, "status"),
                        placeholder="Status",
                        clearable=True,
                    ),
                    dcc.Input(
                        id="search-filter",
                        type="search",
                        placeholder="Search text, chunk, record, note",
                    ),
                ],
                className="filters",
            ),
            html.Section(id="summary", className="stats"),
            html.Main(
                [
                    html.Section(
                        [
                            dash_table.DataTable(
                                id="chunks-table",
                                columns=[
                                    {"name": column, "id": column} for column in REVIEW_COLUMNS
                                ],
                                data=table_rows(rows),
                                page_size=12,
                                sort_action="native",
                                row_selectable="single",
                                selected_rows=[0] if rows else [],
                                style_cell={
                                    "fontFamily": "system-ui, sans-serif",
                                    "fontSize": "13px",
                                    "padding": "8px",
                                    "textAlign": "left",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_header={
                                    "fontWeight": "700",
                                    "backgroundColor": "#eef2f7",
                                },
                                style_data_conditional=[
                                    {"if": {"column_id": "text"}, "minWidth": "360px"},
                                    {"if": {"column_id": "review_note"}, "minWidth": "220px"},
                                ],
                            )
                        ],
                        className="table-panel",
                    ),
                    html.Aside(
                        [
                            html.H2(id="detail-title"),
                            html.Audio(id="audio-player", controls=True),
                            html.Div(id="detail-meta", className="meta"),
                            html.Label("Status", htmlFor="review-status"),
                            dcc.Dropdown(
                                id="review-status",
                                options=[
                                    {"label": status, "value": status}
                                    for status in STATUS_OPTIONS
                                ],
                                clearable=False,
                            ),
                            html.Label("Review Note", htmlFor="review-note"),
                            dcc.Textarea(id="review-note"),
                            html.Button("Apply To Row", id="apply-button", n_clicks=0),
                            html.Div(id="save-message", className="save-message"),
                            html.H3("Text"),
                            html.P(id="detail-text", className="utterance"),
                        ],
                        className="detail-panel",
                    ),
                ],
                className="workspace",
            ),
        ]
    )

    @app.callback(
        Output("chunks-table", "data"),
        Output("chunks-table", "selected_rows"),
        Output("summary", "children"),
        Input("language-filter", "value"),
        Input("content-filter", "value"),
        Input("status-filter", "value"),
        Input("search-filter", "value"),
    )
    def update_table(language: str, content_type: str, status: str, query: str):
        filtered = filter_rows(
            rows,
            language=language or "",
            content_type=content_type or "",
            status=status or "",
            query=query or "",
        )
        selected = [0] if filtered else []
        return table_rows(filtered), selected, summary_cards(rows, filtered)

    @app.callback(
        Output("selected-chunk-id", "data"),
        Input("chunks-table", "derived_virtual_data"),
        Input("chunks-table", "derived_virtual_selected_rows"),
    )
    def select_chunk(visible_rows, selected_rows):
        if not visible_rows or not selected_rows:
            return ""
        index = selected_rows[0]
        if index >= len(visible_rows):
            return ""
        return visible_rows[index].get("chunk_id", "")

    @app.callback(
        Output("detail-title", "children"),
        Output("audio-player", "src"),
        Output("detail-meta", "children"),
        Output("review-status", "value"),
        Output("review-note", "value"),
        Output("detail-text", "children"),
        Input("selected-chunk-id", "data"),
    )
    def update_detail(chunk_id: str):
        if not chunk_id:
            return "No row selected", "", [], STATUS_OPTIONS[0], "", ""
        row = rows_by_id.get(chunk_id)
        if not row:
            return "Missing row", "", [], STATUS_OPTIONS[0], "", ""

        path = audio_paths.get(chunk_id)
        if path and path.exists() and path.stat().st_size < 5_000_000:
            audio_src = data_uri_for_audio(path)
        elif path and path.exists():
            audio_src = f"/review-audio/{quote(chunk_id)}"
        else:
            audio_src = ""

        meta = [
            html.Div(f"language: {row.get('language', '')}"),
            html.Div(f"content: {row.get('content_type', '')}"),
            html.Div(f"duration: {row.get('duration', '')}s"),
            html.Div(f"record: {row.get('record_id', '')}"),
            html.Div(f"source: {row.get('source_site', '')}"),
        ]
        return (
            row.get("chunk_id", ""),
            audio_src,
            meta,
            row.get("status") or RecordStatus.CANDIDATE.value,
            row.get("review_note", ""),
            row.get("text", ""),
        )

    @app.callback(
        Output("save-message", "children"),
        Output("chunks-table", "data", allow_duplicate=True),
        Output("summary", "children", allow_duplicate=True),
        Input("apply-button", "n_clicks"),
        State("selected-chunk-id", "data"),
        State("review-status", "value"),
        State("review-note", "value"),
        State("language-filter", "value"),
        State("content-filter", "value"),
        State("status-filter", "value"),
        State("search-filter", "value"),
        prevent_initial_call=True,
    )
    def apply_review(
        _n_clicks: int,
        chunk_id: str,
        status: str,
        note: str,
        language: str,
        content_type: str,
        status_filter: str,
        query: str,
    ):
        if not chunk_id:
            raise PreventUpdate
        row = rows_by_id.get(chunk_id)
        if not row:
            return "Selected row was not found.", no_update, no_update
        row["status"] = status or RecordStatus.CANDIDATE.value
        row["review_note"] = note or ""
        filtered = filter_rows(
            rows,
            language=language or "",
            content_type=content_type or "",
            status=status_filter or "",
            query=query or "",
        )
        return f"Applied review to {chunk_id}.", table_rows(filtered), summary_cards(rows, filtered)

    @app.callback(
        Output("save-message", "children", allow_duplicate=True),
        Input("save-button", "n_clicks"),
        State("selected-chunk-id", "data"),
        State("review-status", "value"),
        State("review-note", "value"),
        prevent_initial_call=True,
    )
    def save_reviews(_n_clicks: int, chunk_id: str, status: str, note: str):
        if chunk_id and chunk_id in rows_by_id:
            rows_by_id[chunk_id]["status"] = status or RecordStatus.CANDIDATE.value
            rows_by_id[chunk_id]["review_note"] = note or ""
        write_metadata(metadata_path, rows, fieldnames)
        return f"Saved {len(rows):,} rows to {metadata_path}."

    return app


def run_review_ui(metadata_path: Path, *, host: str, port: int, debug: bool) -> None:
    app = build_app(metadata_path)
    app.run(host=host, port=port, debug=debug)
