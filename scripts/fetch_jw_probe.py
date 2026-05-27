#!/usr/bin/env python3
"""Fetch a small JW media probe for one target language.

This is an exploratory script, not the production scraper. It saves the raw JW
media-link response and a compact summary so the archive metadata schema can be
adjusted before the real `jw.org` adapter is implemented.
"""

import argparse
import html
import re
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


API_URL = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"
USER_AGENT = "faso-speech-jw-probe/0.1"


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch JW publication media metadata.")
    parser.add_argument(
        "--language",
        required=True,
        help="Project language label, for example moore, dioula, fulfulde, or gulimancema.",
    )
    parser.add_argument(
        "--jw-language-code",
        required=True,
        help="JW langwritten code used by the JW media API, for example E or F.",
    )
    parser.add_argument(
        "--publication",
        default="nwt",
        help="JW publication code to fetch. Default: nwt.",
    )
    parser.add_argument(
        "--format",
        default="MP3",
        help="Media format to fetch. Default: MP3.",
    )
    parser.add_argument(
        "--output-dir",
        default="tmp/jw_probe",
        help="Directory where raw and summary JSON files are written.",
    )
    parser.add_argument(
        "--fetch-text",
        action="store_true",
        help="Also fetch JW finder pages for sampled Bible chapters and extract verse text.",
    )
    parser.add_argument(
        "--max-text-items",
        type=int,
        default=3,
        help="Maximum media items to fetch text for when --fetch-text is used. Default: 3.",
    )
    return parser.parse_args()


def build_url(publication, jw_language_code, media_format):
    query = {
        "pub": publication,
        "langwritten": jw_language_code,
        "txtCMSLang": jw_language_code,
        "fileformat": media_format,
        "alllangs": "0",
    }
    return f"{API_URL}?{urllib.parse.urlencode(query)}"


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", "replace")
    return json.loads(body)


def fetch_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


class BibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_bible_text = False
        self.current_verse_id = ""
        self.current_parts = []
        self.span_depth = 0
        self.verses = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id") == "bibleText":
            self.in_bible_text = True
            return

        if not self.in_bible_text:
            return

        classes = set(attrs.get("class", "").split())
        if tag == "span" and "verse" in classes and attrs.get("id", "").startswith("v"):
            self.current_verse_id = attrs["id"]
            self.current_parts = []
            self.span_depth = 1
            return

        if self.current_verse_id and tag == "span":
            self.span_depth += 1

    def handle_endtag(self, tag):
        if self.current_verse_id and tag == "span":
            self.span_depth -= 1
            if self.span_depth == 0:
                self.verses.append(
                    {
                        "verse_id": self.current_verse_id,
                        "text": clean_verse_text(" ".join(self.current_parts)),
                    }
                )
                self.current_verse_id = ""
                self.current_parts = []
            return

        if tag == "div" and self.in_bible_text and not self.current_verse_id:
            self.in_bible_text = False

    def handle_data(self, data):
        if self.current_verse_id:
            self.current_parts.append(data)


def clean_verse_text(text):
    text = html.unescape(text)
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"^[\s\d]+", "", text)
    text = text.replace("+", " ").replace("*", " ")
    return " ".join(text.split())


def finder_url(jw_language_code, publication, book_number, chapter):
    bible_ref = f"{int(book_number):02d}{int(chapter):03d}001"
    query = {
        "wtlocale": jw_language_code,
        "prefer": "lang",
        "bible": bible_ref,
        "pub": publication,
    }
    return f"https://www.jw.org/finder?{urllib.parse.urlencode(query)}"


def extract_verses(document):
    parser = BibleTextParser()
    parser.feed(document)
    return [verse for verse in parser.verses if verse["text"]]


def find_audio_items(value):
    items = []

    def walk(node, path):
        if isinstance(node, dict):
            url = node.get("url") or node.get("stream")
            if isinstance(url, str) and url.lower().endswith((".mp3", ".aac", ".m4a")):
                items.append(
                    {
                        "path": ".".join(path),
                        "url": url,
                        "title": node.get("title", ""),
                        "duration": node.get("duration", ""),
                        "filesize": node.get("filesize", ""),
                    }
                )
            for key, child in node.items():
                walk(child, [*path, str(key)])
            return

        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, [*path, str(index)])

    walk(value, [])
    return items


def media_items(data, jw_language_code, media_format):
    if not isinstance(data, dict):
        return []
    files = data.get("files", {})
    if not isinstance(files, dict):
        return []
    language_files = files.get(jw_language_code, {})
    if not isinstance(language_files, dict):
        return []
    items = language_files.get(media_format, [])
    return items if isinstance(items, list) else []


def summarize_media_items(items):
    summaries = []
    for item in items[:20]:
        file_info = item.get("file", {}) if isinstance(item, dict) else {}
        markers_info = item.get("markers", {}) if isinstance(item, dict) else {}
        markers = markers_info.get("markers", []) if isinstance(markers_info, dict) else []
        summaries.append(
            {
                "title": item.get("title", ""),
                "url": file_info.get("url", ""),
                "filesize": item.get("filesize", ""),
                "modified_datetime": file_info.get("modifiedDatetime", ""),
                "checksum": file_info.get("checksum", ""),
                "bible_book_number": markers_info.get("bibleBookNumber", ""),
                "bible_chapter": markers_info.get("bibleBookChapter", ""),
                "marker_count": len(markers) if isinstance(markers, list) else 0,
                "markers_sample": markers[:5] if isinstance(markers, list) else [],
            }
        )
    return summaries


def summarize_response(data, args, url):
    audio_items = find_audio_items(data)
    items = media_items(data, args.jw_language_code, args.format)
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "request_url": url,
        "language": args.language,
        "jw_language_code": args.jw_language_code,
        "publication": args.publication,
        "format": args.format,
        "publication_name": data.get("pubName", "") if isinstance(data, dict) else "",
        "parent_publication_name": data.get("parentPubName", "") if isinstance(data, dict) else "",
        "formatted_date": data.get("formattedDate", "") if isinstance(data, dict) else "",
        "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
        "media_item_count": len(items),
        "media_items_sample": summarize_media_items(items),
        "audio_item_count": len(audio_items),
        "audio_items_sample": audio_items[:20],
    }


def fetch_text_samples(items, args):
    samples = []
    for item in items[: args.max_text_items]:
        markers_info = item.get("markers", {}) if isinstance(item, dict) else {}
        book_number = markers_info.get("bibleBookNumber")
        chapter = markers_info.get("bibleBookChapter")
        if not book_number or not chapter:
            continue

        url = finder_url(args.jw_language_code, args.publication, book_number, chapter)
        document = fetch_text(url)
        verses = extract_verses(document)
        samples.append(
            {
                "url": url,
                "title": item.get("title", ""),
                "bible_book_number": book_number,
                "bible_chapter": chapter,
                "verse_count": len(verses),
                "verses_sample": verses[:5],
            }
        )
    return samples


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir) / args.language
    stem = f"{args.publication}_{args.jw_language_code}_{args.format.lower()}"
    url = build_url(args.publication, args.jw_language_code, args.format)

    try:
        data = fetch_json(url)
    except Exception as error:
        print(f"failed to fetch {url}: {error}", file=sys.stderr)
        return 1

    raw_path = output_dir / f"{stem}.raw.json"
    summary_path = output_dir / f"{stem}.summary.json"
    summary = summarize_response(data, args, url)
    if args.fetch_text:
        items = media_items(data, args.jw_language_code, args.format)
        summary["text_pages_sample"] = fetch_text_samples(items, args)

    write_json(raw_path, data)
    write_json(summary_path, summary)

    print(f"raw: {raw_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
