# Logbooks

These track how the datasets evolved: decisions made, what real data revealed,
fixes applied, and limitations left open. The goal is that the next session
(human or agent) doesn't have to re-derive a source quirk we already found.

## Convention: one logbook per pipeline stage or published dataset, not per language

Findings are almost always driven by a source format or a build step, which
cuts across Mooré, Dioula and Fulfulde. Splitting by stage mirrors the
scripts, so "which logbook do I update" has one obvious answer: whichever
script or metadata file you just touched.

- [`hf-export.md`](hf-export.md) -- `scripts/export_hf_audio_arrow.py`, building and publishing `madoss/faso-speech`.
- [`faso-speech-plus.md`](faso-speech-plus.md) -- `scripts/build_faso_speech_plus.py`, the `MANIFEST` of external sources, `madoss/faso-speech-plus`.
- [`speakers.md`](speakers.md) -- `metadata/speakers.csv`, speaker identification across both datasets.

Add a new logbook when a new source family or pipeline stage is added, not a
new language.

## Language coverage index

| Language | ISO | Logbooks |
| --- | --- | --- |
| Mooré | `mos` | hf-export, faso-speech-plus, speakers |
| Dioula / Jula | `dyu` | hf-export, faso-speech-plus, speakers |
| Bambara | `bam` | faso-speech-plus |
| Fulfulde (Burkina) | `fuh` | hf-export, faso-speech-plus, speakers |
| Other Fula varieties | `fuf`, `fuc`, `ful`, ... | faso-speech-plus, speakers |

## Hub releases

| Repo | Tag | Commit | Meaning |
| --- | --- | --- | --- |
| `madoss/faso-speech` | `v1.0.0` | `fbc4118a` | Last release before `speaker_id`/`gender` columns |
| `madoss/faso-speech-plus` | `v0.1.0` | `a8ee7fba` | Last release before `speaker_id`/`gender` columns |

## Entry format

Dated, terse, newest entry on top. Prefer "what we learned / decided" over
"what the diff was" -- `git log` already has the diff.

```markdown
## 2026-10-02

- Finding or decision, one or two sentences.
- Why it matters / what to check next.
```
