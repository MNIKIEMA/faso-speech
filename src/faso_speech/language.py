from __future__ import annotations

import re

from faso_speech.models import Language


WORD_PATTERN = re.compile(r"[^\W\d_]+(?:[’'][^\W\d_]+)?", re.UNICODE)
FRENCH_WORD_PATTERN = re.compile(
    r"\b("
    r"au|aux|avec|bien|bon|bonne|car|ce|cela|celle|celui|chez|comme|dans|"
    r"chaque|comment|de|des|dit|doucement|du|elle|enfant|est|et|fait|finit|fois|"
    r"il|je|jour|la|le|les|leur|lui|mais|mon|monde|ne|non|nous|on|ou|"
    r"oui|par|pareils|pas|personne|plein|pleure|poule|pour|quand|que|qui|"
    r"sa|sais|scorpion|se|ses|si|singe|sommes|son|sortie|sur|ton|"
    r"travailler|tu|un|une|va|ventre|vous"
    r")\b",
    re.IGNORECASE,
)
SHORT_FRENCH_WORD_PATTERN = re.compile(
    r"^\W*(?:doucement|singe)\W*$",
    re.IGNORECASE | re.UNICODE,
)
SHORT_FRENCH_PHRASE_PATTERN = re.compile(
    r"^\W*(?:"
    r"oui|"
    r"chaque\s+jour|"
    r"elle\s+dit|"
    r"(?:su\s+r|sur)\s+ce\s+fait|"
    r"sommes[-\s]+nous\s+[^\W\d_]+|"
    r"une\s+fois\s+[^\W\d_]+|"
    r"quand\s+.+|"
    r"un\s+jour|"
    r"si\s+non|"
    r"(?:le|la|les|un|une)\s+[^\W\d_]+\s+[^\W\d_]+|"
    r"(?:le|la|les|un|une)\s+[^\W\d_]+(?:\s+et\s+(?:le|la|les|un|une)\s+[^\W\d_]+)?|"
    r"(?:ton|ta|son|sa|mon|ma)\s+[^\W\d_]+\s+est\s+[^\W\d_]+"
    r")\W*$",
    re.IGNORECASE | re.UNICODE,
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
    # TODO: Replace this growing phrase list with page-structure aware language
    # inference. Short fragments like "singe" or "Elle dit" need neighboring
    # blocks/translation order to classify robustly, not only word matching.
    words = WORD_PATTERN.findall(text.lower())
    if not words:
        return False

    french_words = [word for word in words if FRENCH_WORD_PATTERN.fullmatch(word)]
    strong_french_words = [word for word in french_words if word not in WEAK_FRENCH_WORDS]
    has_moore_specific_text = bool(MOORE_SPECIFIC_PATTERN.search(text))

    if has_moore_specific_text and not strong_french_words:
        return False

    return (
        bool(SHORT_FRENCH_WORD_PATTERN.fullmatch(text))
        or bool(SHORT_FRENCH_PHRASE_PATTERN.fullmatch(text))
        or len(strong_french_words) >= 2
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
    if looks_french(text):
        return "french"
    return source_language


def infer_text_language(text: str, source_language: Language) -> Language:
    if looks_french(text):
        return "french"
    return source_language
