# Notes

## Contes audio segmentation heuristic

For the contes audio files, the structure appears to be regular enough to
separate Mooré and French speech without running full forced alignment.

The audio contains several segment types:

```text
music
noise
noEnergy
speech
```

The useful pattern is:

```text
speech  -> Mooré
noEnergy
speech  -> French
music/noise
```

In other words, inside a block delimited by `music` or `noise`, the first speech
segment is generally the Mooré sentence/proverb, then a `noEnergy` pause marks
the boundary, then the next speech segment is generally the French translation.

Example pattern:

```text
music/noise
noEnergy
speech    # Mooré
noEnergy
speech    # French
noEnergy
music/noise
```

This means we can build a rule-based separator:

1. Run `inaSpeechSegmenter` on the audio file.
2. Use `music` and `noise` as block separators.
3. Inside each block, keep only `speech` segments.
4. Assign the first speech segment to Mooré.
5. Assign the next speech segment to French.
6. Use `noEnergy` as the boundary between Mooré and French.

The text files also follow a useful alternating structure:

```text
Mooré line
French translation
Mooré line
French translation
...
```

Some Mooré entries can span multiple text lines before their French translation,
so the text parser should support Mooré continuation lines.

The expected output of a future script could be a CSV like:

```text
audio_file,start,end,language,text
01-B001-001.mp3,5.74,7.56,moore,"1 Koadeng yet tɩ yõor la gẽla ."
01-B001-001.mp3,8.68,12.72,french,"La perdrix dit que tant qu ’ il y a la vie il y a des œufs."
```

This approach will not be word-level alignment. It is a structure-based
segmentation method. It should be enough to split the audio into Mooré/French
utterance-level segments when the recording keeps the same pattern.

Prototype script:

```bash
python preprocessing/align_contes_segments.py \
  --segments datasets/moore/contes_moore/vol5/raw/01-B001-001.segments.csv \
  --text datasets/moore/contes_moore/vol5/raw/01-B001-001.txt
```

The script writes:

```text
datasets/moore/contes_moore/vol5/raw/01-B001-001.aligned.csv
```

It also chunks the matched audio/text pairs into:

```text
datasets/moore/contes_moore/vol5/raw/01-B001-001_chunks
```

Each `ok` row produces one audio chunk and one text file:

```text
01-B001-001_001_moore_001.wav
01-B001-001_001_moore_001.txt
01-B001-001_001_french_002.wav
01-B001-001_001_french_002.txt
```

Important output statuses:

```text
ok             audio speech segment matched to a text line
extra_audio    speech segment exists but no matching text line was available
missing_audio  text line exists but no matching speech segment was available
```

## Direct HTML timing extraction

Some conte web apps already contain exact text/audio alignment metadata. Their
HTML includes a JavaScript timing array:

```text
{ label: "1a", start: 0, end: 2.63 }
```

and matching text elements:

```text
id="T1a"
```

The browser highlight uses these labels to synchronize audio and text. For
those pages, this is better than VAD or forced alignment.

Prototype script:

```bash
python preprocessing/extract_timed_contes_chunks.py --max-pages-per-volume 1
```

Default base URLs:

```text
https://media.ipsapps.org/mos/ora/co1/01-B001-001.html
https://media.ipsapps.org/mos/ora/co2/01-B001-001.html
https://media.ipsapps.org/mos/ora/vol3/01-B001-001.html
https://media.ipsapps.org/mos/ora/vol4//01-B001-001.html
https://media.ipsapps.org/mos/ora/vol5//01-B021-001.html
```

The script follows each page's `Next Chapter` link, downloads the source audio,
extracts matching `timings` and `T<label>` text, cuts audio chunks, writes text
chunks, and stores one `metadata.csv`.

Test result with one page per volume:

```text
co1: skipped because the checked page has no timings/audio metadata
co2: 32 chunks
vol3: 136 chunks
vol4: 100 chunks
vol5: 40 chunks
```

Known caveat: the site-provided alignment can still be incorrect or misleading
on some pages. Example to review:

```text
https://media.ipsapps.org/mos/ora/p1/01-001-003.html
```

That page exposes timing/text metadata, but it points to a longer shared audio
file:

```text
https://storage.googleapis.com/mos-moore/audio/Proverbes moore 1 a 40 avec musique.mp3
```

So the extracted chunks should be treated as candidates and checked before being
accepted into the final corpus.

## Broader sitemap-based scraper

The long-term scraper should start from:

```text
https://mooreburkina.com/fr/sitemap
```

This can give access to content across multiple languages, including:

```text
Mooré
Dioula
Fulfuldé
```

The scraper should avoid making final alignment decisions during crawling.
Instead, it should save a raw, reproducible archive:

```text
raw HTML
audio URL
downloaded audio
extracted text blocks
site-provided timing metadata
source page URL
app page URL
language
content type
metadata
```

Then processing can happen later:

```text
site timings -> candidate chunks
VAD -> validation or fallback chunks
manual review -> accepted/rejected labels
```

This separation is important because some site-provided timings may be wrong.
If all raw data is saved, alignment and chunking can be improved without
scraping the website again.

Possible raw layout:

```text
raw_sources/
  moore/
    contes/
      vol5/
        01-B021-001/
          page.html
          audio.mp3
          timings.csv
          text.csv
          metadata.json
```

Possible processed layout:

```text
processed/
  html_timing_chunks/
  vad_chunks/
  reviewed_chunks/
  metadata.csv
```
