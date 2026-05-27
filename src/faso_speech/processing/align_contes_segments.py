import argparse
import csv
import subprocess
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Map contes speech segments to alternating Mooré/French text."
    )
    parser.add_argument("--segments", required=True, help="inaSpeechSegmenter CSV file")
    parser.add_argument("--text", required=True, help="Text file scraped for the same audio")
    parser.add_argument(
        "--audio",
        help="Source audio file to chunk. Defaults to <text_stem>.mp3 next to the text file.",
    )
    parser.add_argument(
        "--output",
        help="Output CSV path. Defaults to <text_stem>.aligned.csv next to the text file.",
    )
    parser.add_argument(
        "--chunks-dir",
        help="Folder for chunked audio/text files. Defaults to <text_stem>_chunks next to the text file.",
    )
    parser.add_argument(
        "--audio-format",
        choices=["wav", "mp3"],
        default="wav",
        help="Audio format for chunks. Default: wav",
    )
    parser.add_argument(
        "--start-padding",
        type=float,
        default=0.15,
        help="Seconds to include before each chunk start. Default: 0.15",
    )
    parser.add_argument(
        "--end-padding",
        type=float,
        default=0.15,
        help="Seconds to include after each chunk end. Default: 0.15",
    )
    parser.add_argument(
        "--first-language",
        choices=["moore", "french"],
        default="moore",
        help="Language of the first speech segment. Default: moore",
    )
    return parser.parse_args()


def normalize_text(text):
    return " ".join(text.strip().split())


def starts_with_number(text):
    return text.strip()[:1].isdigit()


def read_text_pairs(path):
    pairs = []
    current_moore = None
    current_following_lines = []

    with open(path, encoding="utf-8") as input_file:
        lines = [normalize_text(line) for line in input_file if line.strip()]

    def flush_current_pair():
        if not current_moore:
            return
        moore_lines = [current_moore]
        french = ""
        if current_following_lines:
            moore_lines.extend(current_following_lines[:-1])
            french = current_following_lines[-1]
        pairs.append(
            {
                "moore": " ".join(moore_lines),
                "french": french,
            }
        )

    for line in lines:
        if starts_with_number(line):
            flush_current_pair()
            current_moore = line
            current_following_lines = []
        elif current_moore:
            current_following_lines.append(line)
        else:
            current_moore = line
            current_following_lines = []

    flush_current_pair()

    return pairs


def read_segments(path):
    segments = []
    with open(path, newline="", encoding="utf-8") as input_file:
        for row in csv.DictReader(input_file):
            row["start"] = float(row["start"])
            row["end"] = float(row["end"])
            row["duration"] = float(row["duration"])
            segments.append(row)
    return segments


def read_speech_segments(path):
    speech = []
    for row in read_segments(path):
        if row["label"] != "speech":
            continue
        speech.append(
            {
                "start": row["start"],
                "end": row["end"],
                "duration": row["duration"],
            }
        )
    return speech


def flatten_pairs(pairs):
    units = []
    for pair_index, pair in enumerate(pairs, start=1):
        units.append(
            {
                "pair_index": pair_index,
                "language": "moore",
                "text": pair["moore"],
            }
        )
        if pair["french"]:
            units.append(
                {
                    "pair_index": pair_index,
                    "language": "french",
                    "text": pair["french"],
                }
            )
    return units


def label_speech_segments(speech_segments, first_language):
    languages = ["moore", "french"]
    if first_language == "french":
        languages.reverse()

    labeled_segments = []
    for index, segment in enumerate(speech_segments):
        labeled_segments.append(
            {
                **segment,
                "language": languages[index % 2],
                "speech_index": index + 1,
            }
        )
    return labeled_segments


def label_speech_segments_by_block(segments, first_language):
    languages = ["moore", "french"]
    if first_language == "french":
        languages.reverse()

    labeled_segments = []
    block_speech_index = 0
    for segment in segments:
        if segment["label"] in {"music", "noise"}:
            block_speech_index = 0
            continue
        if segment["label"] != "speech":
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


def assign_segments(units, speech_segments):
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


def format_assignment(assignment, audio_file):
    segment = assignment["segment"]
    if not segment:
        return {
            "audio_file": audio_file,
            "chunk_audio": "",
            "chunk_text": "",
            "pair_index": assignment["pair_index"],
            "language": assignment["language"],
            "speech_index": "",
            "start": "",
            "end": "",
            "duration": "",
            "status": assignment["status"],
            "text": assignment["text"],
        }

    return {
        "audio_file": audio_file,
        "chunk_audio": "",
        "chunk_text": "",
        "pair_index": assignment["pair_index"],
        "language": assignment["language"],
        "speech_index": segment["speech_index"],
        "start": round(segment["start"], 3),
        "end": round(segment["end"], 3),
        "duration": round(segment["duration"], 3),
        "status": assignment["status"],
        "text": assignment["text"],
    }


def write_csv(path, rows):
    fieldnames = [
        "audio_file",
        "chunk_audio",
        "chunk_text",
        "pair_index",
        "language",
        "speech_index",
        "start",
        "end",
        "duration",
        "status",
        "text",
    ]
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def chunk_filename(row):
    return (
        f"{Path(row['audio_file']).stem}_"
        f"{int(row['pair_index']):03d}_"
        f"{row['language']}_"
        f"{int(row['speech_index']):03d}"
    )


def cut_audio(input_audio, output_audio, start, end, audio_format, start_padding, end_padding):
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    padded_start = max(0.0, start - start_padding)
    padded_end = end + end_padding
    duration = padded_end - padded_start
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(padded_start),
        "-i",
        str(input_audio),
        "-t",
        str(duration),
    ]
    if audio_format == "wav":
        command.extend(["-ac", "1", "-ar", "16000"])
    else:
        command.extend(["-c:a", "libmp3lame", "-q:a", "2"])
    command.append(str(output_audio))
    subprocess.run(command, check=True)


def write_chunk_text(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        output_file.write(f"{row['text']}\n")


def cleanup_existing_chunks(chunks_dir, audio_stem):
    if not chunks_dir.exists():
        return
    for path in chunks_dir.glob(f"{audio_stem}_*"):
        if path.suffix in {".wav", ".mp3", ".txt"}:
            path.unlink()


def write_chunks(rows, input_audio, chunks_dir, audio_format, start_padding, end_padding):
    chunks_dir.mkdir(parents=True, exist_ok=True)
    cleanup_existing_chunks(chunks_dir, input_audio.stem)
    for row in rows:
        if row["status"] != "ok":
            row["chunk_audio"] = ""
            row["chunk_text"] = ""
            continue

        stem = chunk_filename(row)
        audio_path = chunks_dir / f"{stem}.{audio_format}"
        text_path = chunks_dir / f"{stem}.txt"

        cut_audio(
            input_audio,
            audio_path,
            row["start"],
            row["end"],
            audio_format,
            start_padding,
            end_padding,
        )
        write_chunk_text(text_path, row)

        row["chunk_audio"] = str(audio_path)
        row["chunk_text"] = str(text_path)


def main():
    args = parse_args()
    segments_path = Path(args.segments)
    text_path = Path(args.text)
    audio_path = Path(args.audio) if args.audio else text_path.with_suffix(".mp3")
    output_path = Path(args.output) if args.output else text_path.with_suffix(".aligned.csv")
    chunks_dir = (
        Path(args.chunks_dir)
        if args.chunks_dir
        else text_path.with_name(f"{text_path.stem}_chunks")
    )

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    pairs = read_text_pairs(text_path)
    units = flatten_pairs(pairs)
    speech_segments = label_speech_segments_by_block(
        read_segments(segments_path),
        args.first_language,
    )

    assignments = assign_segments(units, speech_segments)
    audio_file = audio_path.name
    rows = [format_assignment(assignment, audio_file) for assignment in assignments]
    write_chunks(
        rows,
        audio_path,
        chunks_dir,
        args.audio_format,
        args.start_padding,
        args.end_padding,
    )
    write_csv(output_path, rows)

    print(f"Text pairs: {len(pairs)}")
    print(f"Text units: {len(units)}")
    print(f"Speech segments: {len(speech_segments)}")
    print(f"Chunks written to: {chunks_dir}")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
