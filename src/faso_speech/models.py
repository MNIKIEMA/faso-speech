from __future__ import annotations

from enum import StrEnum
from typing import Literal

import msgspec


Language = Literal["moore", "dioula", "fulfulde", "gulimancema", "french"]
ContentType = Literal["contes", "proverbes", "devinettes", "poemes", "bible", "dictionary"]
SourceSite = Literal["mooreburkina.com", "jw.org", "bible.com", "webonary.org"]
Parser = Literal["app_builder", "jw", "bible_com", "webonary"]


class RecordStatus(StrEnum):
    ARCHIVED = "archived"
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    NEEDS_ALIGNMENT = "needs_alignment"
    MISSING_AUDIO = "missing_audio"
    MISSING_TEXT = "missing_text"
    MISSING_TIMING = "missing_timing"
    TIMING_MISMATCH = "timing_mismatch"
    PARSER_ERROR = "parser_error"
    DOWNLOAD_ERROR = "download_error"


class CatalogEntry(msgspec.Struct):
    id: str
    language: Language
    content_type: ContentType
    source_site: SourceSite
    source_url: str
    parser: Parser
    priority: int
    notes: str = ""
    app_url: str = ""
    volume_start: int = 0
    volume_end: int = 0
    has_audio: bool = True
    has_timing: bool = True
    has_markers: bool = False
    audio_format: str = "wav"
    include_french: bool = True
    license: str = "unknown"
    attribution: str = "unknown"


class SourceRecord(msgspec.Struct):
    catalog_id: str
    source_url: str
    source_site: SourceSite
    language: Language
    content_type: ContentType
    app_url: str = ""
    audio_url: str = ""
    parser: Parser = "app_builder"
    license: str = "unknown"
    attribution: str = "unknown"


class Timing(msgspec.Struct):
    label: str
    start: float
    end: float
    duration: float


class TextBlock(msgspec.Struct):
    label: str
    text: str
    language: Language


class ParsedPage(msgspec.Struct):
    source_url: str
    app_url: str
    title: str
    audio_url: str
    text_blocks: list[TextBlock]
    timings: list[Timing]
    next_page: str = ""
    warnings: list[str] = []


class ArchiveRecord(msgspec.Struct):
    record_id: str
    catalog_id: str
    language: Language
    content_type: ContentType
    source_site: SourceSite
    source_url: str
    app_url: str
    parser: Parser
    title: str
    audio_url: str
    audio_path: str
    app_html_path: str
    text_path: str
    timings_path: str
    markers_path: str
    has_audio: bool
    has_timing: bool
    has_markers: bool
    status: RecordStatus
    warnings: list[str]
    scraped_at: str
    source_html_path: str = ""
    license: str = "unknown"
    attribution: str = "unknown"
