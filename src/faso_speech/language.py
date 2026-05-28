from __future__ import annotations

import re

from faso_speech.models import Language


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
    r"\b(?:c|d|j|l|m|n|qu|s)[’'][A-Za-zÀ-ÖØ-öø-ÿ]+",
    re.IGNORECASE,
)


def looks_french(text: str) -> bool:
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", text.lower())
    if not words:
        return False
    french_words = sum(1 for word in words if FRENCH_WORD_PATTERN.fullmatch(word))
    return (
        french_words >= 2
        or bool(FRENCH_ACCENT_PATTERN.search(text))
        or bool(FRENCH_CONTRACTION_PATTERN.search(text))
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
