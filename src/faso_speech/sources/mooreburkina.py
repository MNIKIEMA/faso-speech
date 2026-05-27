from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup

from faso_speech.http import fetch_text
from faso_speech.models import CatalogEntry, SourceRecord


def app_name(app_url: str) -> str:
    parts = [part for part in urllib.parse.urlsplit(app_url).path.split("/") if part]
    if app_url.rstrip("/").endswith(".html"):
        return parts[-2] if len(parts) >= 2 else "app"
    return parts[-1] if parts else "app"


def page_stem(app_url: str) -> str:
    stem = urllib.parse.urlsplit(app_url).path.rstrip("/").split("/")[-1]
    if stem.endswith(".html"):
        return stem.removesuffix(".html")
    return stem or "page"


def find_app_url(source_html: str, source_url: str) -> str:
    soup = BeautifulSoup(source_html, "lxml")
    iframe = soup.select_one("iframe[src*='media.ipsapps.org']")
    if iframe and iframe.get("src"):
        return urllib.parse.urljoin(source_url, iframe["src"])
    link = soup.select_one("a[href*='media.ipsapps.org']")
    if link and link.get("href"):
        return urllib.parse.urljoin(source_url, link["href"])
    return ""


def resolve_app_url(app_url: str, timeout: int = 30) -> tuple[str, str]:
    html = fetch_text(app_url, timeout=timeout)
    if app_url.rstrip("/").endswith(".html"):
        return app_url, html

    match = re.search(r"location\.href\s*=\s*['\"](?P<href>[^'\"]+)['\"]", html)
    if not match:
        return app_url, html
    resolved = urllib.parse.urljoin(app_url, match.group("href"))
    return resolved, fetch_text(resolved, timeout=timeout)


def discover_record(
    entry: CatalogEntry,
    *,
    save_source_html: bool = False,
    timeout: int = 30,
) -> tuple[SourceRecord, str, str]:
    source_html = ""
    app_url = entry.app_url
    if not app_url:
        source_html = fetch_text(entry.source_url, timeout=timeout)
        app_url = find_app_url(source_html, entry.source_url)
    elif save_source_html:
        source_html = fetch_text(entry.source_url, timeout=timeout)

    if not app_url:
        raise ValueError(f"no app URL found for catalog entry {entry.id}")

    resolved_app_url, app_html = resolve_app_url(app_url, timeout=timeout)
    record = SourceRecord(
        catalog_id=entry.id,
        source_url=entry.source_url,
        source_site=entry.source_site,
        language=entry.language,
        content_type=entry.content_type,
        app_url=resolved_app_url,
        parser=entry.parser,
        license=entry.license,
        attribution=entry.attribution,
    )
    return record, app_html, source_html
