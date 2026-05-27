from __future__ import annotations

import subprocess
from pathlib import Path


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
    if audio_format == "wav":
        command.extend(["-ac", "1", "-ar", "16000"])
    else:
        command.extend(["-c:a", "libmp3lame", "-q:a", "2"])
    command.append(str(output_audio))
    subprocess.run(command, check=True)
