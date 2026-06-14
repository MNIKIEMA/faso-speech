from __future__ import annotations

import subprocess
from pathlib import Path


def audio_format_options(audio_format: str) -> list[str]:
    if audio_format == "wav":
        return ["-ac", "1", "-ar", "16000"]
    return ["-c:a", "libmp3lame", "-q:a", "2"]


def audio_duration(input_audio: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_audio),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def concat_audio_segments(
    input_audio: Path,
    output_audio: Path,
    *,
    segments: list[tuple[float, float]],
    audio_format: str = "wav",
) -> None:
    if not segments:
        raise ValueError("At least one audio segment is required.")
    if len(segments) == 1:
        start, end = segments[0]
        cut_audio(
            input_audio,
            output_audio,
            start=start,
            end=end,
            audio_format=audio_format,
        )
        return

    output_audio.parent.mkdir(parents=True, exist_ok=True)
    trim_filters = []
    concat_inputs = []
    for index, (start, end) in enumerate(segments):
        trim_filters.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]"
        )
        concat_inputs.append(f"[a{index}]")
    filter_complex = (
        ";".join(trim_filters)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={len(segments)}:v=0:a=1[out]"
    )
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_audio),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
    ]
    command.extend(audio_format_options(audio_format))
    command.append(str(output_audio))
    subprocess.run(command, check=True)


def cut_audio(
    input_audio: Path,
    output_audio: Path,
    *,
    start: float,
    end: float,
    audio_format: str = "wav",
    start_padding: float = 0.0,
    end_padding: float = 0.0,
) -> None:
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    padded_start = max(0.0, start - start_padding)
    padded_end = end + end_padding
    duration = max(0.0, padded_end - padded_start)
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
    command.extend(audio_format_options(audio_format))
    command.append(str(output_audio))
    subprocess.run(command, check=True)
