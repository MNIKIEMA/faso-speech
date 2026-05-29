from __future__ import annotations

from collections.abc import Iterable

from faso_speech.models import CatalogEntry


CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        id="moore-contes-vol1",
        language="moore",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/collection-2-12-contes-en-moor%C3%A9",
        app_url="https://media.ipsapps.org/mos/ora/co1/",
        parser="app_builder",
        priority=1,
        notes="Moore Burkina Mooré contes volume 1.",
    ),
    CatalogEntry(
        id="moore-contes-vol2",
        language="moore",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-et-proverbes-en-moor%C3%A9/contes-en-moor%C3%A9",
        app_url="https://media.ipsapps.org/mos/ora/co2/",
        parser="app_builder",
        priority=1,
        notes="Moore Burkina Mooré contes volume 2.",
    ),
    CatalogEntry(
        id="moore-contes-vol3",
        language="moore",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-proverbes/contes-vol-3-avec-audio",
        app_url="https://media.ipsapps.org/mos/ora/vol3/",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Mooré contes volume 3.",
    ),
    CatalogEntry(
        id="moore-contes-vol4",
        language="moore",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-proverbes/contes-vol-4-avec-audio",
        app_url="https://media.ipsapps.org/mos/ora/vol4/",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Mooré contes volume 4.",
    ),
    CatalogEntry(
        id="moore-contes-vol5",
        language="moore",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-proverbes/contes-vol-5-avec-fran%C3%A7ais",
        app_url="https://media.ipsapps.org/mos/ora/vol5/",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Mooré contes volume 5.",
    ),
    CatalogEntry(
        id="moore-proverbes-vol1",
        language="moore",
        content_type="proverbes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-et-proverbes-en-moor%C3%A9/proverbes-en-moor%C3%A9-vol-1",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Mooré proverbes, discover app URL from source page.",
    ),
    CatalogEntry(
        id="moore-devinettes",
        language="moore",
        content_type="devinettes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/contes-proverbes/devinettes-en-moor%C3%A9",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Mooré devinettes, discover app URL from source page.",
    ),
    CatalogEntry(
        id="dioula-contes-vol1",
        language="dioula",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/dioula/5-contes-dioula",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Dioula contes volume 1.",
    ),
    CatalogEntry(
        id="dioula-contes-vol2",
        language="dioula",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/dioula/contes-en-dioula-avec-audio-volume-2",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Dioula contes volume 2.",
    ),
    CatalogEntry(
        id="fulfulde-contes-vol1",
        language="fulfulde",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/fulfulde/contes-lus-en-fulfulde",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Fulfuldé contes volume 1.",
    ),
    CatalogEntry(
        id="fulfulde-contes-vol2",
        language="fulfulde",
        content_type="contes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/fulfulde/15-contes-en-fulfulde",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Fulfuldé 15 contes.",
    ),
    CatalogEntry(
        id="fulfulde-proverbes-vol1",
        language="fulfulde",
        content_type="proverbes",
        source_site="mooreburkina.com",
        source_url="https://mooreburkina.com/fr/fulfulde/proverbes-fulfulde-avec-audio",
        parser="app_builder",
        priority=2,
        notes="Moore Burkina Fulfuldé proverbes volume 1.",
    ),
]


def parse_filter(filter_expr: str) -> dict[str, str]:
    if not filter_expr:
        return {}
    filters = {}
    for item in filter_expr.split():
        key, separator, value = item.partition("=")
        if not separator:
            raise ValueError(f"invalid filter item: {item!r}")
        filters[key] = value
    return filters


def list_entries(catalog_id: str = "", filter_expr: str = "") -> list[CatalogEntry]:
    entries: Iterable[CatalogEntry] = CATALOG
    if catalog_id:
        entries = [entry for entry in entries if entry.id == catalog_id]
    filters = parse_filter(filter_expr)
    for key, value in filters.items():
        entries = [entry for entry in entries if str(getattr(entry, key, "")) == value]
    return list(entries)
