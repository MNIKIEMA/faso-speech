# Speakers (`metadata/speakers.csv`)

One row per `catalog_id` from `data/processed/metadata.csv`. This is the
single place to edit speaker knowledge for `faso-speech`; the export joins it
on `catalog_id` and `faso-speech-plus` picks it up from the published
`faso-speech` columns. Columns: `catalog_id, speaker_id, gender, status,
speaker_name, evidence, notes`. Only `speaker_id` and `gender` are published;
`speaker_name` stays in the repo.

## 2026-10-02

- inaSpeechSegmenter gives gender per speech segment but not speaker
  identity. Once segments are re-run with gender, aggregate per catalog to
  sanity-check the listening-based genders above and to fill unknown ones
  (Dioula vol2, Fulfulde catalogs) -- treat model gender as a hint, not proof.
- Mooré speakers come from the maintainer's listening checks: vol2 one male
  (`mos-spk-01`); vol3 one female (`mos-spk-02`), reused in vol4; vol5 one
  female different from vol3 (`mos-spk-03`); proverbes one male different from
  vol2 (`mos-spk-05`).
- Devinettes is female and sounds close to vol3 but is **unconfirmed**. It got
  its own ID (`mos-spk-04`) on purpose: wrongly merging two speakers is worse
  than splitting one, especially for speaker-disjoint train/validation splits.
  Change it to `mos-spk-02` once confirmed.
- Dioula readers are credited on the mooreburkina source pages
  (`data/raw_sources/dioula/contes/co{1,2}/source.html`, meta description):
  vol1 "lus par l'auteur Mme Dakuyo Aïssata / Sanou" (`dyu-spk-01`), vol2
  "© audio par Maïmouna Guira" (`dyu-spk-02`, gender not stated).
- Names in audio filenames, not confirmed anywhere else: "Kinda" in
  `NN Kinda cont vol 1|2.mp3` (Mooré vol3/vol4), "Absa" in
  `NN Ful cont Absa.mp3` (fulfulde-contes-vol1, `fuh-spk-01`, unconfirmed).
- False leads, do not reuse: `KABORÉ Timothée` on the Mooré proverbs page is
  the translator, not the voice; `Conte_01_Nikeema.mp3` is the story title
  (*Nin-kẽema*); `kibare` in transcripts means "story". Dioula-digits
  filenames are upload uniqids, not speaker IDs. App pages (`app.html`) carry
  no credits.
- Still unknown: `fulfulde-contes-vol2`, `fulfulde-proverbes-vol1`.
- External sources (checked through the HF viewer `/info`, `/statistics`,
  `/first-rows` endpoints only -- don't download shards just to inspect):
  WaxalNLP `ful_asr` has 207 real speaker IDs (gender column empty);
  Omnilingual has `spkNN` per language config (8 for `fuh`); Koumankan4Dyula
  has `gender` (`M`/`F`), age group and country but no speaker ID; FLEURS has
  gender only; Dyula Bible has `SPEAKER_NN` labels that look like diarization
  output (10 distinct, numbering gaps) and are left unmapped until shown to be
  consistent across chapters. AfriSpeech, `moore_audio_data`,
  `merged-bambara-dioula` and `Fula-pular` have nothing.
