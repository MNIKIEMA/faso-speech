from __future__ import annotations

import argparse
import csv
from pathlib import Path

from faso_speech.audio import audio_duration, concat_audio_segments, cut_audio
from faso_speech.processing.segment import (
    assign_segments,
    flatten_pairs,
    label_speech_segments_by_block,
    read_segments,
    read_text_pairs,
    run_inaspeechsegmenter,
)


METADATA_COLUMNS = [
    "file_name",
    "text",
    "language",
    "duration",
    "char_per_second",
    "source_audio",
    "start",
    "end",
    "pair_index",
    "speech_index",
]

SEGMENT_COLUMNS = ["label", "start", "end", "duration"]
SOURCE_LANGUAGES = {"moore", "fulfulde", "dioula"}
MAX_WHOLE_AUDIO_SECONDS = 30.0


def chars_per_second(text: str, duration: float) -> float:
    return len(text) / duration if duration > 0 else 0.0


def apply_padding(
    start: float,
    end: float,
    start_padding: float,
    end_padding: float,
) -> tuple[float, float]:
    return max(0.0, start - start_padding), end + end_padding


def write_segments_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=SEGMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_metadata(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=METADATA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def chunk_stem(audio_path: Path, speech_index: int | None = None) -> str:
    if speech_index is None:
        return audio_path.stem
    return f"{audio_path.stem}_{speech_index:03d}"


def source_text(pairs: list[dict[str, str]]) -> str:
    return " ".join(pair["source"] for pair in pairs if pair["source"])


def append_metadata_row(
    rows: list[dict[str, object]],
    *,
    output_dir: Path,
    chunk_audio: Path,
    text: str,
    language: str,
    source_audio: Path,
    start: float,
    end: float,
    pair_index: int | str,
    speech_index: int | str,
) -> None:
    duration = max(0.0, end - start)
    rows.append(
        {
            "file_name": str(chunk_audio.relative_to(output_dir)),
            "text": text,
            "language": language,
            "duration": round(duration, 3),
            "char_per_second": round(chars_per_second(text, duration), 3),
            "source_audio": str(source_audio),
            "start": round(start, 3),
            "end": round(end, 3),
            "pair_index": pair_index,
            "speech_index": speech_index,
        }
    )


def segment_ranges(segments: list[dict[str, object]]) -> list[tuple[float, float]]:
    return [(float(segment["start"]), float(segment["end"])) for segment in segments]


def total_segment_duration(segments: list[dict[str, object]]) -> float:
    return sum(max(0.0, end - start) for start, end in segment_ranges(segments))


def prepare_segmented_dataset(
    *,
    audio_path: Path,
    text_path: Path,
    output_dir: Path,
    segments_path: Path | None = None,
    language: str = "moore",
    audio_format: str = "wav",
    start_padding: float = 0.0,
    end_padding: float = 0.0,
    min_char_per_second: float = 0.0,
    max_char_per_second: float = 0.0,
) -> int:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if not text_path.exists():
        raise FileNotFoundError(f"Transcript file not found: {text_path}")
    if language not in SOURCE_LANGUAGES:
        choices = ", ".join(sorted(SOURCE_LANGUAGES))
        raise ValueError(f"Unsupported source language: {language}. Expected one of: {choices}")

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = output_dir / "chunks"
    metadata_path = output_dir / "metadata.csv"
    generated_segments_path = output_dir / f"{audio_path.stem}.segments.csv"
    pairs = read_text_pairs(text_path)
    source_duration = audio_duration(audio_path)
    metadata_rows: list[dict[str, object]] = []

    if segments_path:
        segments = read_segments(segments_path)
    else:
        segments = run_inaspeechsegmenter(audio_path)
        write_segments_csv(generated_segments_path, segments)

    speech_segments = label_speech_segments_by_block(
        segments,
        first_language=language,
        second_language="french",
    )

    if source_duration <= MAX_WHOLE_AUDIO_SECONDS:
        text = source_text(pairs)
        if not text:
            write_metadata(metadata_path, metadata_rows)
            return 0
        source_speech_segments = [
            segment for segment in speech_segments if segment["language"] == language
        ]
        cleaned_duration = total_segment_duration(source_speech_segments)
        if cleaned_duration <= 0:
            write_metadata(metadata_path, metadata_rows)
            return 0
        char_rate = chars_per_second(text, cleaned_duration)
        if char_rate < min_char_per_second:
            write_metadata(metadata_path, metadata_rows)
            return 0
        if max_char_per_second > 0 and char_rate > max_char_per_second:
            write_metadata(metadata_path, metadata_rows)
            return 0

        chunk_audio = chunks_dir / f"{chunk_stem(audio_path)}.{audio_format}"
        concat_audio_segments(
            audio_path,
            chunk_audio,
            segments=segment_ranges(source_speech_segments),
            audio_format=audio_format,
        )
        append_metadata_row(
            metadata_rows,
            output_dir=output_dir,
            chunk_audio=chunk_audio,
            text=text,
            language=language,
            source_audio=audio_path,
            start=0.0,
            end=cleaned_duration,
            pair_index="",
            speech_index="",
        )
        write_metadata(metadata_path, metadata_rows)
        return len(metadata_rows)

    units = flatten_pairs(
        pairs,
        source_language=language,
        translation_language="french",
    )
    assignments = assign_segments(units, speech_segments)

    for assignment in assignments:
        segment = assignment["segment"]
        if assignment["status"] != "ok" or not segment:
            continue
        if assignment["language"] != language:
            continue
        text = assignment["text"]
        start, end = apply_padding(
            float(segment["start"]),
            float(segment["end"]),
            start_padding,
            end_padding,
        )
        char_rate = chars_per_second(text, max(0.0, end - start))
        if char_rate < min_char_per_second:
            continue
        if max_char_per_second > 0 and char_rate > max_char_per_second:
            continue

        chunk_audio = chunks_dir / f"{chunk_stem(audio_path, int(segment['speech_index']))}.{audio_format}"
        cut_audio(
            audio_path,
            chunk_audio,
            start=start,
            end=end,
            audio_format=audio_format,
            start_padding=0.0,
            end_padding=0.0,
        )
        append_metadata_row(
            metadata_rows,
            output_dir=output_dir,
            chunk_audio=chunk_audio,
            text=text,
            language=language,
            source_audio=audio_path,
            start=start,
            end=end,
            pair_index=assignment["pair_index"],
            speech_index=segment["speech_index"],
        )

    write_metadata(metadata_path, metadata_rows)
    return len(metadata_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare segmented audio/text chunks and dataset metadata."
    )
    parser.add_argument("--audio", required=True, help="Source audio file to segment and chunk.")
    parser.add_argument("--text", required=True, help="Transcript text file for the audio.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory. Writes audio chunks and metadata.csv inside this folder.",
    )
    parser.add_argument(
        "--segments",
        help="Optional existing inaSpeechSegmenter CSV. If omitted, inaSpeechSegmenter is run.",
    )
    parser.add_argument(
        "--language",
        default="moore",
        choices=["moore", "fulfulde", "dioula"],
        help="Source language to export. French translations are used only for alignment. Default: moore.",
    )
    parser.add_argument(
        "--audio-format",
        choices=["wav", "mp3"],
        default="wav",
        help="Audio format for dataset chunks. Default: wav.",
    )
    parser.add_argument(
        "--start-padding",
        type=float,
        default=0.15,
        help="Seconds to include before each chunk start. Default: 0.15.",
    )
    parser.add_argument(
        "--end-padding",
        type=float,
        default=0.15,
        help="Seconds to include after each chunk end. Default: 0.15.",
    )
    parser.add_argument(
        "--min-char-per-second",
        type=float,
        default=0.0,
        help="Drop rows below this character-per-second value. Default: 0.0.",
    )
    parser.add_argument(
        "--max-char-per-second",
        type=float,
        default=0.0,
        help="Drop rows above this character-per-second value. Default: disabled.",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    count = prepare_segmented_dataset(
        audio_path=Path(args.audio),
        text_path=Path(args.text),
        output_dir=Path(args.output_dir),
        segments_path=Path(args.segments) if args.segments else None,
        language=args.language,
        audio_format=args.audio_format,
        start_padding=args.start_padding,
        end_padding=args.end_padding,
        min_char_per_second=args.min_char_per_second,
        max_char_per_second=args.max_char_per_second,
    )
    print(f"training_rows={count}")
    print(f"metadata={Path(args.output_dir) / 'metadata.csv'}")


if __name__ == "__main__":
    main()
