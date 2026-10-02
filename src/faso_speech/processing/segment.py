from __future__ import annotations

import csv
import re
from pathlib import Path


segmenter = None

def load_segmenter():
    global segmenter
    if segmenter:
        return segmenter
    from inaSpeechSegmenter import Segmenter

    segmenter = Segmenter()
    return segmenter


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def remove_leading_transcript_digit(text: str) -> str:
    return re.sub(r"^\s*\d+[\s.):-]*", "", text, count=1).strip()


def starts_with_number(text: str) -> bool:
    return text.strip()[:1].isdigit()


def read_text_pairs(path: Path) -> list[dict[str, str]]:
    pairs = []
    current_source = None
    current_following_lines = []

    with path.open(encoding="utf-8") as input_file:
        lines = [normalize_text(line) for line in input_file if line.strip()]

    def flush_current_pair() -> None:
        if not current_source:
            return
        source_lines = [remove_leading_transcript_digit(current_source)]
        translation = ""
        if current_following_lines:
            source_lines.extend(current_following_lines[:-1])
            translation = current_following_lines[-1]
        pairs.append(
            {
                "source": " ".join(source_lines),
                "translation": translation,
            }
        )

    for line in lines:
        if starts_with_number(line):
            flush_current_pair()
            current_source = line
            current_following_lines = []
        elif current_source:
            current_following_lines.append(line)
        else:
            current_source = line
            current_following_lines = []

    flush_current_pair()

    return pairs


def run_inaspeechsegmenter(audio_path: Path) -> list[dict[str, float | str]]:
    segmenter = load_segmenter()
    rows = []
    for label, start, end in segmenter(str(audio_path)):
        start = float(start)
        end = float(end)
        rows.append(
            {
                "label": normalize_segment_label(str(label)),
                "start": start,
                "end": end,
                "duration": max(0.0, end - start),
                "gender": segment_gender(str(label)),
            }
        )
    return rows


def read_segments(path: Path) -> list[dict[str, float | str]]:
    segments = []
    with path.open(newline="", encoding="utf-8") as input_file:
        for row in csv.DictReader(input_file):
            row["label"] = normalize_segment_label(row["label"])
            row["start"] = float(row["start"])
            row["end"] = float(row["end"])
            row["duration"] = float(row["duration"])
            segments.append(row)
    return segments


def segment_gender(label: str) -> str:
    """Keep inaSpeechSegmenter's male/female speech label before normalization."""
    normalized = label.strip()
    return normalized if normalized in {"male", "female"} else ""


def normalize_segment_label(label: str) -> str:
    normalized = label.strip()
    if normalized in {"speech", "male", "female"}:
        return "speech"
    if normalized.lower() in {"noenergy", "no_energy", "silence"}:
        return "noise"
    return normalized


def flatten_pairs(
    pairs: list[dict[str, str]],
    *,
    source_language: str,
    translation_language: str,
) -> list[dict[str, object]]:
    units = []
    for pair_index, pair in enumerate(pairs, start=1):
        units.append(
            {
                "pair_index": pair_index,
                "language": source_language,
                "text": pair["source"],
            }
        )
        if pair["translation"]:
            units.append(
                {
                    "pair_index": pair_index,
                    "language": translation_language,
                    "text": pair["translation"],
                }
            )
    return units


def label_speech_segments_by_block(
    segments: list[dict[str, float | str]],
    *,
    first_language: str,
    second_language: str,
) -> list[dict[str, object]]:
    languages = [first_language, second_language]
    labeled_segments = []
    block_speech_index = 0

    for segment in segments:
        label = normalize_segment_label(str(segment["label"]))
        if label in {"music", "noise"}:
            block_speech_index = 0
            continue
        if label != "speech":
            continue

        labeled_segments.append(
            {
                "start": segment["start"],
                "end": segment["end"],
                "duration": segment["duration"],
                "language": languages[block_speech_index % 2],
                "speech_index": len(labeled_segments) + 1,
            }
        )
        block_speech_index += 1

    return labeled_segments


def assign_segments(
    units: list[dict[str, object]],
    speech_segments: list[dict[str, object]],
) -> list[dict[str, object]]:
    assignments = []
    unit_index = 0
    speech_index = 0

    while unit_index < len(units) or speech_index < len(speech_segments):
        unit = units[unit_index] if unit_index < len(units) else None
        segment = speech_segments[speech_index] if speech_index < len(speech_segments) else None

        if unit and segment and unit["language"] == segment["language"]:
            assignments.append(
                {
                    "pair_index": unit["pair_index"],
                    "language": unit["language"],
                    "text": unit["text"],
                    "segment": segment,
                    "status": "ok",
                }
            )
            unit_index += 1
            speech_index += 1
            continue

        if unit and segment:
            assignments.append(
                {
                    "pair_index": "",
                    "language": segment["language"],
                    "text": "",
                    "segment": segment,
                    "status": "extra_audio",
                }
            )
            speech_index += 1
            continue

        if unit:
            assignments.append(
                {
                    "pair_index": unit["pair_index"],
                    "language": unit["language"],
                    "text": unit["text"],
                    "segment": None,
                    "status": "missing_audio",
                }
            )
            unit_index += 1
            continue

        assignments.append(
            {
                "pair_index": "",
                "language": segment["language"],
                "text": "",
                "segment": segment,
                "status": "extra_audio",
            }
        )
        speech_index += 1

    return assignments
