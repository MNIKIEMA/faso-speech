from __future__ import annotations

import re

from faso_speech.models import Language


WORD_PATTERN = re.compile(r"[^\W\d_]+(?:[’'][^\W\d_]+)?", re.UNICODE)
FRENCH_WORD_PATTERN = re.compile(
    r"\b("
    r"au|aux|avec|bien|bon|bonne|car|ce|cela|celle|celui|chez|comme|dans|"
    r"de|des|du|elle|est|et|il|je|le|les|leur|lui|mais|non|nous|on|ou|"
    r"par|pas|pour|que|qui|sa|sais|se|ses|son|sur|tu|un|une|vous"
    r")\b",
    re.IGNORECASE,
)
FRENCH_ACCENT_PATTERN = re.compile(r"[àâçéèêëîïôùûüœ]", re.IGNORECASE)
FRENCH_CONTRACTION_PATTERN = re.compile(
    r"\b(?:c|d|j|l|m|n|qu|s)[’'][^\W\d_]+",
    re.IGNORECASE,
)
MOORE_SPECIFIC_PATTERN = re.compile(r"[ɛƐɩƖẽẼĩĨõÕũŨãÃ]")
WEAK_FRENCH_WORDS = {
    "ce",
    "de",
    "du",
    "et",
    "il",
    "je",
    "le",
    "on",
    "ou",
    "sa",
    "se",
    "tu",
    "un",
}


def looks_french(text: str) -> bool:
    words = WORD_PATTERN.findall(text.lower())
    if not words:
        return False

    french_words = [word for word in words if FRENCH_WORD_PATTERN.fullmatch(word)]
    strong_french_words = [word for word in french_words if word not in WEAK_FRENCH_WORDS]
    has_moore_specific_text = bool(MOORE_SPECIFIC_PATTERN.search(text))

    if has_moore_specific_text and not strong_french_words:
        return False

    return (
        len(strong_french_words) >= 2
        or len(french_words) >= 4
        or (len(strong_french_words) >= 1 and len(french_words) >= 3)
        or bool(FRENCH_CONTRACTION_PATTERN.search(text))
        or (bool(FRENCH_ACCENT_PATTERN.search(text)) and not has_moore_specific_text)
    )


def infer_app_builder_language(
    *,
    node_html: str,
    text: str,
    source_language: Language,
) -> Language:
    if "bdit" in node_html and looks_french(text):
        return "french"
    return source_language


def infer_text_language(text: str, source_language: Language) -> Language:
    if looks_french(text):
        return "french"
    return source_language
