import importlib.util
import sys
import types
from pathlib import Path


def load_export_module(monkeypatch):
    pyarrow = types.ModuleType("pyarrow")
    pyarrow.field = lambda *args, **kwargs: (args, kwargs)
    pyarrow.struct = lambda fields: fields
    pyarrow.binary = lambda: bytes
    pyarrow.string = lambda: str
    pyarrow.array = lambda values, type=None: values
    pyarrow.table = lambda columns: columns

    datasets = types.ModuleType("datasets")
    datasets.Audio = lambda *args, **kwargs: ("Audio", args, kwargs)
    datasets.Dataset = object
    datasets.DatasetInfo = lambda *args, **kwargs: ("DatasetInfo", args, kwargs)
    datasets.Features = dict
    datasets.Value = lambda *args, **kwargs: ("Value", args, kwargs)

    dataset_dict = types.ModuleType("datasets.dataset_dict")
    dataset_dict.DatasetDict = dict

    table = types.ModuleType("datasets.table")
    table.InMemoryTable = lambda value: value

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    monkeypatch.setitem(sys.modules, "pyarrow", pyarrow)
    monkeypatch.setitem(sys.modules, "datasets", datasets)
    monkeypatch.setitem(sys.modules, "datasets.dataset_dict", dataset_dict)
    monkeypatch.setitem(sys.modules, "datasets.table", table)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)

    module_path = Path(__file__).parents[1] / "scripts" / "export_hf_audio_arrow.py"
    spec = importlib.util.spec_from_file_location("export_hf_audio_arrow", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_audio_payload_applies_segments_when_csv_exists(tmp_path, monkeypatch):
    export = load_export_module(monkeypatch)
    input_dir = tmp_path / "processed"
    audio = input_dir / "moore" / "contes" / "timed_chunks" / "chunks" / "chunk.wav"
    segments = input_dir / "moore" / "contes" / "segments" / "chunk.segments.csv"
    audio.parent.mkdir(parents=True)
    segments.parent.mkdir(parents=True)
    audio.write_bytes(b"original")
    segments.write_text(
        "label,start,end,duration\n"
        "noise,0.0,0.5,0.5\n"
        "speech,0.5,1.25,0.75\n",
        encoding="utf-8",
    )
    calls = []

    def fake_segment_audio_bytes(path, ranges):
        calls.append((path, ranges))
        return b"segmented"

    monkeypatch.setattr(export, "segment_audio_bytes", fake_segment_audio_bytes)

    payload, row = export.audio_payload(
        input_dir,
        {
            "chunk_id": "chunk",
            "language": "moore",
            "content_type": "contes",
            "duration": "1.25",
        },
        audio,
        str(audio),
        apply_segments=True,
    )

    assert payload == {"bytes": b"segmented", "path": "chunk.segmented.wav"}
    assert row["duration"] == "1.15"
    assert calls == [(audio, [(0.35, 1.5)])]


def test_audio_payload_keeps_original_when_segments_are_missing(tmp_path, monkeypatch):
    export = load_export_module(monkeypatch)
    input_dir = tmp_path / "processed"
    audio = input_dir / "chunk.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"original")

    payload, row = export.audio_payload(
        input_dir,
        {"chunk_id": "chunk", "language": "moore", "content_type": "contes"},
        audio,
        str(audio),
        apply_segments=True,
    )

    assert payload == {"bytes": b"original", "path": "chunk.wav"}
    assert row["chunk_id"] == "chunk"


def test_export_ranges_limit_music_padding_and_merge_short_non_music_gap(
    tmp_path,
    monkeypatch,
):
    export = load_export_module(monkeypatch)
    segments = tmp_path / "chunk.segments.csv"
    segments.write_text(
        "label,start,end,duration\n"
        "music,0.0,1.0,1.0\n"
        "speech,1.0,2.0,1.0\n"
        "noise,2.0,2.3,0.3\n"
        "speech,2.3,3.0,0.7\n"
        "music,3.0,3.4,0.4\n"
        "speech,3.4,4.0,0.6\n",
        encoding="utf-8",
    )

    ranges = export.export_ranges_from_segments(
        segments,
        start_padding=0.15,
        end_padding=0.25,
        music_start_padding=0.05,
        music_end_padding=0.05,
        max_intra_segment_gap=0.50,
        max_music_gap=0.05,
    )

    assert ranges == [(0.95, 3.05), (3.35, 4.25)]


def test_export_ranges_cut_long_non_music_gap(tmp_path, monkeypatch):
    export = load_export_module(monkeypatch)
    segments = tmp_path / "chunk.segments.csv"
    segments.write_text(
        "label,start,end,duration\n"
        "speech,0.5,1.0,0.5\n"
        "noise,1.0,2.0,1.0\n"
        "speech,2.0,2.5,0.5\n",
        encoding="utf-8",
    )

    ranges = export.export_ranges_from_segments(
        segments,
        start_padding=0.1,
        end_padding=0.1,
        music_start_padding=0.05,
        music_end_padding=0.05,
        max_intra_segment_gap=0.50,
        max_music_gap=0.05,
    )

    assert ranges == [(0.4, 1.1), (1.9, 2.6)]


def test_attach_speakers_joins_on_catalog_id(tmp_path, monkeypatch):
    export = load_export_module(monkeypatch)
    speakers_csv = tmp_path / "speakers.csv"
    speakers_csv.write_text(
        "catalog_id,speaker_id,gender,status,speaker_name,evidence,notes\n"
        "moore-contes-vol3,mos-spk-02,female,confirmed,,,\n"
        "dioula-contes-vol2,dyu-spk-02,,confirmed,,,\n"
        "fulfulde-contes-vol2,,,unknown,,,\n",
        encoding="utf-8",
    )

    rows = export.attach_speakers(
        [
            {"chunk_id": "a", "catalog_id": "moore-contes-vol3"},
            {"chunk_id": "b", "catalog_id": "dioula-contes-vol2"},
            {"chunk_id": "c", "catalog_id": "fulfulde-contes-vol2"},
        ],
        export.read_speakers(speakers_csv),
    )

    assert [(row["speaker_id"], row["gender"]) for row in rows] == [
        ("mos-spk-02", "female"),
        ("dyu-spk-02", None),
        (None, None),
    ]


def test_attach_speakers_is_noop_without_speakers_file(tmp_path, monkeypatch):
    export = load_export_module(monkeypatch)
    rows = [{"chunk_id": "a", "catalog_id": "moore-contes-vol3"}]

    assert export.attach_speakers(rows, export.read_speakers(tmp_path / "missing.csv")) == rows
