import csv

import faso_speech.processing.segment_dataset as segment_dataset
from faso_speech.processing.segment import (
    label_speech_segments_by_block,
    read_text_pairs,
    remove_leading_transcript_digit,
)
from faso_speech.processing.segment_dataset import apply_padding, chars_per_second


def test_chars_per_second_handles_positive_and_zero_duration():
    assert chars_per_second("abcdef", 2.0) == 3.0
    assert chars_per_second("abcdef", 0.0) == 0.0


def test_apply_padding_clamps_start_to_zero():
    assert apply_padding(1.0, 3.0, 0.25, 0.5) == (0.75, 3.5)
    assert apply_padding(0.1, 3.0, 0.25, 0.5) == (0.0, 3.5)


def test_remove_leading_transcript_digit():
    assert remove_leading_transcript_digit("1 La parole") == "La parole"
    assert remove_leading_transcript_digit("12. La parole") == "La parole"
    assert remove_leading_transcript_digit("La parole 1") == "La parole 1"


def test_read_text_pairs_removes_number_from_moore_line(tmp_path):
    transcript = tmp_path / "story.txt"
    transcript.write_text(
        "1 Mam yida.\n"
        "Je suis content.\n"
        "2 A waame.\n"
        "Il est venu.\n",
        encoding="utf-8",
    )

    assert read_text_pairs(transcript) == [
        {"source": "Mam yida.", "translation": "Je suis content."},
        {"source": "A waame.", "translation": "Il est venu."},
    ]


def test_no_energy_starts_a_new_language_block():
    segments = [
        {"label": "speech", "start": 0.0, "end": 1.0, "duration": 1.0},
        {"label": "speech", "start": 1.0, "end": 2.0, "duration": 1.0},
        {"label": "noEnergy", "start": 2.0, "end": 3.0, "duration": 1.0},
        {"label": "speech", "start": 3.0, "end": 4.0, "duration": 1.0},
    ]

    labeled = label_speech_segments_by_block(
        segments,
        first_language="moore",
        second_language="french",
    )

    assert [segment["language"] for segment in labeled] == ["moore", "french", "moore"]


def test_huggingface_metadata_uses_padded_chunk_times(tmp_path, monkeypatch):
    audio = tmp_path / "story.wav"
    audio.write_bytes(b"")
    transcript = tmp_path / "story.txt"
    transcript.write_text("1 Mam yida.\nJe suis content.\n", encoding="utf-8")
    segments = tmp_path / "segments.csv"
    segments.write_text(
        "label,start,end,duration\n"
        "speech,1.0,3.0,2.0\n"
        "speech,3.5,5.0,1.5\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "hf"
    cut_calls = []

    def fake_cut_audio(*args, **kwargs):
        cut_calls.append((args, kwargs))

    monkeypatch.setattr(segment_dataset, "cut_audio", fake_cut_audio)
    monkeypatch.setattr(segment_dataset, "audio_duration", lambda _path: 60.0)

    count = segment_dataset.prepare_segmented_dataset(
        audio_path=audio,
        text_path=transcript,
        output_dir=output_dir,
        segments_path=segments,
        start_padding=0.25,
        end_padding=0.5,
    )

    assert count == 1
    assert cut_calls[0][0][1] == output_dir / "chunks" / "story_001.wav"
    assert cut_calls[0][1]["start"] == 0.75
    assert cut_calls[0][1]["end"] == 3.5
    assert cut_calls[0][1]["start_padding"] == 0.0
    assert cut_calls[0][1]["end_padding"] == 0.0

    with (output_dir / "metadata.csv").open(newline="", encoding="utf-8") as metadata_file:
        row = next(csv.DictReader(metadata_file))

    assert row["start"] == "0.75"
    assert row["end"] == "3.5"
    assert row["duration"] == "2.75"
    assert row["char_per_second"] == "3.273"
    assert row["file_name"] == "chunks/story_001.wav"


def test_short_audio_keeps_original_stem(tmp_path, monkeypatch):
    audio = tmp_path / "story.wav"
    audio.write_bytes(b"")
    transcript = tmp_path / "story.txt"
    transcript.write_text("1 Mam yida.\nJe suis content.\n", encoding="utf-8")
    segments = tmp_path / "segments.csv"
    segments.write_text(
        "label,start,end,duration\n"
        "speech,1.0,3.0,2.0\n"
        "noEnergy,3.0,8.0,5.0\n"
        "speech,8.0,10.0,2.0\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "hf"
    concat_calls = []

    def fake_concat_audio_segments(*args, **kwargs):
        concat_calls.append((args, kwargs))

    monkeypatch.setattr(segment_dataset, "concat_audio_segments", fake_concat_audio_segments)
    monkeypatch.setattr(segment_dataset, "audio_duration", lambda _path: 25.0)

    count = segment_dataset.prepare_segmented_dataset(
        audio_path=audio,
        text_path=transcript,
        output_dir=output_dir,
        segments_path=segments,
    )

    assert count == 1
    assert concat_calls[0][0][1] == output_dir / "chunks" / "story.wav"
    assert concat_calls[0][1]["segments"] == [(1.0, 3.0), (8.0, 10.0)]

    with (output_dir / "metadata.csv").open(newline="", encoding="utf-8") as metadata_file:
        row = next(csv.DictReader(metadata_file))

    assert row["file_name"] == "chunks/story.wav"
    assert row["text"] == "Mam yida."
    assert row["start"] == "0.0"
    assert row["end"] == "4.0"
    assert row["duration"] == "4.0"
    assert row["pair_index"] == ""
    assert row["speech_index"] == ""
