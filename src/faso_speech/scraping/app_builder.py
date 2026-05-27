import csv
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


USER_AGENT = "Mozilla/5.0"


def safe_url(url):
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    query = urllib.parse.quote(parts.query, safe="=&%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def fetch_text(url, timeout=30):
    request = urllib.request.Request(safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def download_file(url, output_path, timeout=60):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        output_path.write_bytes(response.read())


def page_stem(url):
    return Path(urllib.parse.urlsplit(url).path).stem


def app_name(url):
    parts = [part for part in urllib.parse.urlsplit(url).path.split("/") if part]
    return parts[-2] if len(parts) >= 2 else "app"


def parse_title(document):
    match = re.search(r"<title>(?P<title>.*?)</title>", document, flags=re.DOTALL)
    if not match:
        return ""
    return " ".join(html.unescape(match.group("title")).split())


def parse_timings(document):
    return [
        {
            "label": match.group("label"),
            "start": float(match.group("start")),
            "end": float(match.group("end")),
            "duration": round(float(match.group("end")) - float(match.group("start")), 3),
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


def infer_language_from_fragment(fragment):
    if "bdit" in fragment:
        return "french"
    return ""


def parse_text_blocks(document):
    blocks = []
    for match in re.finditer(
        r"<div\s+id=['\"]T(?P<label>[^'\"]+)['\"][^>]*class=['\"][^'\"]*\btxs\b[^'\"]*['\"][^>]*>"
        r"(?P<body>.*?)</div>",
        document,
        flags=re.DOTALL,
    ):
        body = match.group("body")
        blocks.append(
            {
                "label": match.group("label"),
                "language_hint": infer_language_from_fragment(body),
                "text": clean_html_text(body),
            }
        )
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


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
