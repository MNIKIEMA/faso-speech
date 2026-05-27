import argparse
import urllib.parse
from pathlib import Path

from faso_speech.scraping.app_builder import (
    app_name,
    download_file,
    page_stem,
    parse_audio_url,
    parse_next_url,
    parse_text_blocks,
    parse_timings,
    parse_title,
    write_csv,
    write_json,
)
from faso_speech.scraping.app_builder import fetch_text
from faso_speech.scraping.discovery import MOOREBURKINA_SITEMAP_URL, discover_app_urls_from_sitemap


DEFAULT_SEED_URLS = [
    "https://media.ipsapps.org/mos/ora/co1/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/co2/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol3/01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol4//01-B001-001.html",
    "https://media.ipsapps.org/mos/ora/vol5//01-B021-001.html",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Archive raw app-builder speech pages with HTML, audio, timings, and text."
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw_sources",
        help="Root directory for raw archived pages. Default: data/raw_sources",
    )
    parser.add_argument(
        "--seed-url",
        action="append",
        dest="seed_urls",
        help="App page URL to archive. Can be passed multiple times.",
    )
    parser.add_argument(
        "--use-default-seeds",
        action="store_true",
        help="Archive the built-in Mooré conte seed URLs.",
    )
    parser.add_argument(
        "--from-sitemap",
        action="store_true",
        help="Discover app URLs from the Moore Burkina sitemap.",
    )
    parser.add_argument(
        "--sitemap-url",
        default=MOOREBURKINA_SITEMAP_URL,
        help="Sitemap URL to use with --from-sitemap.",
    )
    parser.add_argument(
        "--max-source-pages",
        type=int,
        help="Limit Moore Burkina source pages inspected while discovering app URLs.",
    )
    parser.add_argument(
        "--max-pages-per-seed",
        type=int,
        help="Limit chapter pages followed per seed URL.",
    )
    parser.add_argument(
        "--language",
        default="unknown",
        help="Language label to store in metadata when it cannot be inferred.",
    )
    parser.add_argument(
        "--content-type",
        default="unknown",
        help="Content type label to store in metadata.",
    )
    parser.add_argument(
        "--download-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download audio files while archiving. Default: true.",
    )
    return parser.parse_args()


def archive_page(page_url, output_dir, language, content_type, download_audio=True):
    document = fetch_text(page_url)
    timings = parse_timings(document)
    text_blocks = parse_text_blocks(document)
    audio_url = parse_audio_url(document, page_url)
    next_url = parse_next_url(document, page_url)
    app = app_name(page_url)
    stem = page_stem(page_url)
    page_dir = output_dir / language / content_type / app / stem
    page_dir.mkdir(parents=True, exist_ok=True)

    html_path = page_dir / "page.html"
    html_path.write_text(document, encoding="utf-8")

    audio_path = ""
    if download_audio and audio_url:
        suffix = Path(urllib.parse.urlsplit(audio_url).path).suffix or ".mp3"
        audio_file = page_dir / f"audio{suffix}"
        if not audio_file.exists():
            download_file(audio_url, audio_file)
        audio_path = str(audio_file)

    write_csv(
        page_dir / "timings.csv",
        timings,
        ["label", "start", "end", "duration"],
    )
    write_csv(
        page_dir / "text.csv",
        text_blocks,
        ["label", "language_hint", "text"],
    )

    metadata = {
        "page_url": page_url,
        "next_url": next_url,
        "title": parse_title(document),
        "app": app,
        "page": stem,
        "language": language,
        "content_type": content_type,
        "audio_url": audio_url,
        "audio_path": audio_path,
        "html_path": str(html_path),
        "timings_path": str(page_dir / "timings.csv"),
        "text_path": str(page_dir / "text.csv"),
        "timing_count": len(timings),
        "text_count": len(text_blocks),
        "has_audio": bool(audio_url),
    }
    write_json(page_dir / "metadata.json", metadata)
    return metadata


def collect_seed_urls(args):
    seed_urls = list(args.seed_urls or [])
    if args.use_default_seeds:
        seed_urls.extend(DEFAULT_SEED_URLS)
    if args.from_sitemap:
        seed_urls.extend(
            discover_app_urls_from_sitemap(
                args.sitemap_url,
                max_source_pages=args.max_source_pages,
            )
        )
    return sorted(set(seed_urls))


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    seed_urls = collect_seed_urls(args)
    if not seed_urls:
        seed_urls = DEFAULT_SEED_URLS

    all_metadata = []
    for seed_url in seed_urls:
        seen = set()
        page_url = seed_url
        page_count = 0
        print(f"\nSeed: {seed_url}")

        while page_url and page_url not in seen:
            if args.max_pages_per_seed and page_count >= args.max_pages_per_seed:
                break
            seen.add(page_url)
            page_count += 1

            try:
                metadata = archive_page(
                    page_url,
                    output_dir,
                    args.language,
                    args.content_type,
                    download_audio=args.download_audio,
                )
            except Exception as error:
                print(f"  failed: {page_url}: {error}")
                break

            all_metadata.append(metadata)
            print(
                f"  {metadata['app']}/{metadata['page']}: "
                f"timings={metadata['timing_count']} "
                f"text={metadata['text_count']} "
                f"audio={metadata['has_audio']}"
            )
            page_url = metadata["next_url"]

    index_rows = [
        {
            "language": item["language"],
            "content_type": item["content_type"],
            "app": item["app"],
            "page": item["page"],
            "page_url": item["page_url"],
            "audio_url": item["audio_url"],
            "audio_path": item["audio_path"],
            "html_path": item["html_path"],
            "timings_path": item["timings_path"],
            "text_path": item["text_path"],
            "timing_count": item["timing_count"],
            "text_count": item["text_count"],
            "has_audio": item["has_audio"],
        }
        for item in all_metadata
    ]
    write_csv(
        output_dir / "index.csv",
        index_rows,
        [
            "language",
            "content_type",
            "app",
            "page",
            "page_url",
            "audio_url",
            "audio_path",
            "html_path",
            "timings_path",
            "text_path",
            "timing_count",
            "text_count",
            "has_audio",
        ],
    )
    print(f"\nArchived pages: {len(all_metadata)}")
    print(f"Index written to: {output_dir / 'index.csv'}")


if __name__ == "__main__":
    main()
