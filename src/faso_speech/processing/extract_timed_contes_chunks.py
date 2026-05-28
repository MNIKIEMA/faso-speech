import argparse
import csv
import html
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from faso_speech.language import infer_app_builder_language


BASE_URLS = [
    "https://media.ipsapps.org/mos/ora/co1/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/co2/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol3/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol4//01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol5//01-B021-001.html",
]

USER_AGENT = "Mozilla/5.0"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract exact conte audio/text chunks from app-builder HTML timings."
    )
    parser.add_argument(
        "--output-dir",
        default="datasets/moore/contes_moore/timed_chunks",
        help="Folder where audio/text chunks and metadata CSVs are written.",
    )
    parser.add_argument(
        "--max-pages-per-volume",
        type=int,
        help="Optional limit for testing one or a few pages per base URL.",
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
        default=0.0,
        help="Seconds to include before each timing start. Default: 0.0",
    )
    parser.add_argument(
        "--end-padding",
        type=float,
        default=0.0,
        help="Seconds to include after each timing end. Default: 0.0",
    )
    return parser.parse_args()


def safe_url(url):
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    query = urllib.parse.quote(parts.query, safe="=&%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def fetch_text(url):
    request = urllib.request.Request(safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def download_file(url, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        output_path.write_bytes(response.read())


def volume_name(base_url):
    parts = [part for part in urllib.parse.urlsplit(base_url).path.split("/") if part]
    return parts[-2] if len(parts) >= 2 else "volume"


def page_stem(url):
    return Path(urllib.parse.urlsplit(url).path).stem


def parse_timings(document):
    return [
        {
            "label": match.group("label"),
            "start": float(match.group("start")),
            "end": float(match.group("end")),
        }
        for match in re.finditer(
            r"\{\s*label:\s*['\"](?P<label>[^'\"]+)['\"]\s*,\s*"
            r"start:\s*(?P<start>\d+(?:\.\d+)?)\s*,\s*"
            r"end:\s*(?P<end>\d+(?:\.\d+)?)\s*\}",
            document,
        )
    ]


def clean_html_text(fragment):
    fragment = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def infer_language(fragment, text):
    return infer_app_builder_language(
        node_html=fragment,
        text=text,
        source_language="moore",
    )


def parse_text_blocks(document):
    blocks = {}
    for match in re.finditer(
        r"<div\s+id=['\"]T(?P<label>[^'\"]+)['\"][^>]*class=['\"][^'\"]*\btxs\b[^'\"]*['\"][^>]*>"
        r"(?P<body>.*?)</div>",
        document,
        flags=re.DOTALL,
    ):
        body = match.group("body")
        text = clean_html_text(body)
        blocks[match.group("label")] = {
            "text": text,
            "language": infer_language(body, text),
        }
    return blocks


def parse_audio_url(document, page_url):
    match = re.search(r"<source[^>]+src=['\"](?P<src>[^'\"]+)['\"]", document)
    if not match:
        return ""
    return urllib.parse.urljoin(page_url, html.unescape(match.group("src")))


def parse_next_url(document, page_url):
    match = re.search(
        r"<a\s+href=['\"](?P<href>[^'\"]+)['\"]\s+title=['\"]Next Chapter['\"]",
        document,
    )
    if not match:
        return ""
    return urllib.parse.urljoin(page_url, html.unescape(match.group("href")))


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


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        output_file.write(f"{text}\n")


def extract_page(page_url, output_dir, audio_format, start_padding, end_padding):
    document = fetch_text(page_url)
    timings = parse_timings(document)
    text_blocks = parse_text_blocks(document)
    audio_url = parse_audio_url(document, page_url)
    next_url = parse_next_url(document, page_url)

    if not timings or not text_blocks or not audio_url:
        return [], next_url, {
            "page_url": page_url,
            "timings": len(timings),
            "text_blocks": len(text_blocks),
            "audio_url": audio_url,
            "skipped": True,
        }

    vol_name = volume_name(page_url)
    stem = page_stem(page_url)
    volume_dir = output_dir / vol_name
    audio_dir = volume_dir / "audio"
    chunk_dir = volume_dir / "chunks"
    audio_ext = Path(urllib.parse.urlsplit(audio_url).path).suffix or ".mp3"
    source_audio = audio_dir / f"{stem}{audio_ext}"
    if not source_audio.exists():
        download_file(audio_url, source_audio)

    rows = []
    for index, timing in enumerate(timings, start=1):
        block = text_blocks.get(timing["label"])
        if not block or not block["text"]:
            continue

        chunk_stem = f"{stem}_{index:03d}_{timing['label']}"
        chunk_audio = chunk_dir / f"{chunk_stem}.{audio_format}"
        chunk_text = chunk_dir / f"{chunk_stem}.txt"
        cut_audio(
            source_audio,
            chunk_audio,
            timing["start"],
            timing["end"],
            audio_format,
            start_padding,
            end_padding,
        )
        write_text(chunk_text, block["text"])

        rows.append(
            {
                "volume": vol_name,
                "page": stem,
                "page_url": page_url,
                "source_audio": str(source_audio),
                "audio_url": audio_url,
                "label": timing["label"],
                "start": timing["start"],
                "end": timing["end"],
                "duration": round(timing["end"] - timing["start"], 3),
                "language": block["language"],
                "chunk_audio": str(chunk_audio),
                "chunk_text": str(chunk_text),
                "text": block["text"],
            }
        )

    return rows, next_url, {
        "page_url": page_url,
        "timings": len(timings),
        "text_blocks": len(text_blocks),
        "audio_url": audio_url,
        "skipped": False,
    }


def write_metadata(path, rows):
    fieldnames = [
        "volume",
        "page",
        "page_url",
        "source_audio",
        "audio_url",
        "label",
        "start",
        "end",
        "duration",
        "language",
        "chunk_audio",
        "chunk_text",
        "text",
    ]
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    all_rows = []

    for base_url in BASE_URLS:
        seen = set()
        page_url = base_url
        page_count = 0
        print(f"\nVolume start: {base_url}")

        while page_url and page_url not in seen:
            if args.max_pages_per_volume and page_count >= args.max_pages_per_volume:
                break
            seen.add(page_url)
            page_count += 1

            rows, next_url, info = extract_page(
                page_url,
                output_dir,
                args.audio_format,
                args.start_padding,
                args.end_padding,
            )
            all_rows.extend(rows)
            status = "skipped" if info["skipped"] else f"{len(rows)} chunks"
            print(
                f"  {page_stem(page_url)}: {status} "
                f"(timings={info['timings']}, text={info['text_blocks']})"
            )
            page_url = next_url

    metadata_path = output_dir / "metadata.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_metadata(metadata_path, all_rows)
    print(f"\nTotal chunks: {len(all_rows)}")
    print(f"Metadata written to: {metadata_path}")


if __name__ == "__main__":
    main()
