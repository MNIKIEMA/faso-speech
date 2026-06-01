from faso_speech.language import infer_app_builder_language, infer_text_language, looks_french
from faso_speech.extraction import processing_language
from faso_speech.scraping.app_builder import parse_text_blocks


def test_moore_sentence_with_shared_french_stopwords_stays_moore():
    text = "n le wẽ yɛsa:"

    assert not looks_french(text)
    assert infer_text_language(text, "moore") == "moore"
    assert (
        infer_app_builder_language(
            node_html='<div class="txs bdit" id="T1">n le wẽ yɛsa:</div>',
            text=text,
            source_language="moore",
        )
        == "moore"
    )


def test_french_translation_with_function_words_is_french():
    text = "La perdrix dit que tant qu il y a la vie il y a des oeufs."

    assert looks_french(text)
    assert infer_text_language(text, "moore") == "french"


def test_legacy_app_builder_scraper_does_not_trust_bdit_alone():
    html = """
    <div id="T1" class="txs bdit">n le wẽ yɛsa:</div>
    <div id="T2" class="txs bdit">C'est bon.</div>
    """

    assert parse_text_blocks(html) == [
        {"label": "1", "language_hint": "", "text": "n le wẽ yɛsa:"},
        {"label": "2", "language_hint": "french", "text": "C'est bon."},
    ]


def test_extraction_trusts_archived_text_language():
    language, review_note = processing_language(
        {"language": "moore", "text": "Le y n wa."},
        {"language": "moore"},
    )

    assert language == "moore"
    assert review_note == ""
