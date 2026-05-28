from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup

from faso_speech.language import infer_app_builder_language
from faso_speech.models import Language, ParsedPage, SourceRecord, TextBlock, Timing


TIMING_PATTERN = re.compile(
    r"\{\s*label:\s*['\"](?P<label>[^'\"]+)['\"]\s*,\s*"
    r"start:\s*(?P<start>\d+(?:\.\d+)?)\s*,\s*"
    r"end:\s*(?P<end>\d+(?:\.\d+)?)\s*\}"
)


def parse_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if not soup.title:
        return ""
    return " ".join(soup.title.get_text(" ", strip=True).split())


def parse_timings(html: str) -> list[Timing]:
    timings = []
    for match in TIMING_PATTERN.finditer(html):
        start = float(match.group("start"))
        end = float(match.group("end"))
        timings.append(
            Timing(
                label=match.group("label"),
                start=start,
                end=end,
                duration=round(end - start, 3),
            )
        )
    return timings


def parse_text_blocks(html: str, source_language: Language) -> list[TextBlock]:
    soup = BeautifulSoup(html, "lxml")
    blocks = []
    for node in soup.select("div.txs[id^='T']"):
        label = node.get("id", "").removeprefix("T")
        text = " ".join(node.get_text(" ", strip=True).split())
        if not label or not text:
            continue
        blocks.append(
            TextBlock(
                label=label,
                text=text,
                language=infer_app_builder_language(
                    node_html=str(node),
                    text=text,
                    source_language=source_language,
                ),
            )
        )
    return blocks


def parse_audio_url(html: str, app_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    source = soup.select_one("audio source[src], source[src]")
    if not source:
        return ""
    return urllib.parse.urljoin(app_url, source.get("src", ""))


def parse_next_url(html: str, app_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", attrs={"title": "Next Chapter"})
    if not next_link:
        return ""
    href = next_link.get("href", "")
    if not href:
        return ""
    return urllib.parse.urljoin(app_url, href)


def parse_page(html: str, record: SourceRecord) -> ParsedPage:
    timings = parse_timings(html)
    text_blocks = parse_text_blocks(html, record.language)
    warnings = []
    if not timings:
        warnings.append("missing_timing")
    if not text_blocks:
        warnings.append("missing_text")

    return ParsedPage(
        source_url=record.source_url,
        app_url=record.app_url,
        title=parse_title(html),
        audio_url=parse_audio_url(html, record.app_url),
        text_blocks=text_blocks,
        timings=timings,
        next_page=parse_next_url(html, record.app_url),
        warnings=warnings,
    )
