import csv

from faso_speech.processing.segment_processed import discover_segmentation_jobs


def test_discover_segmentation_jobs_uses_chunk_audio_from_metadata(tmp_path):
    processed = tmp_path / "processed"
    chunk_audio = processed / "moore" / "contes" / "timed_chunks" / "chunks" / "chunk_001.wav"
    chunk_audio.parent.mkdir(parents=True)
    chunk_audio.write_bytes(b"")
    metadata = processed / "metadata.csv"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    with metadata.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=["chunk_audio", "language", "content_type", "chunk_id"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "chunk_audio": str(chunk_audio),
                "language": "moore",
                "content_type": "contes",
                "chunk_id": "moore-contes-vol1-01-B001-001_001_1a",
            }
        )
        writer.writerow(
            {
                "chunk_audio": str(chunk_audio),
                "language": "moore",
                "content_type": "contes",
                "chunk_id": "moore-contes-vol1-01-B001-001_001_1a",
            }
        )

    jobs = discover_segmentation_jobs(processed)

    assert len(jobs) == 1
    assert jobs[0].audio_path == chunk_audio
    assert jobs[0].output_csv == (
        processed
        / "moore"
        / "contes"
        / "segments"
        / "moore-contes-vol1-01-B001-001_001_1a.segments.csv"
    )


def test_discover_segmentation_jobs_scans_audio_when_metadata_is_missing(tmp_path):
    processed = tmp_path / "processed"
    audio = processed / "moore" / "contes" / "source.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"")
    ignored = processed / "moore" / "contes" / "source.txt"
    ignored.write_text("not audio", encoding="utf-8")

    jobs = discover_segmentation_jobs(processed)

    assert len(jobs) == 1
    assert jobs[0].audio_path == audio
    assert jobs[0].output_csv == processed / "segments" / "moore" / "contes" / "source.segments.csv"


def test_discover_segmentation_jobs_filters_metadata_by_language_and_content_type(tmp_path):
    processed = tmp_path / "processed"
    metadata = processed / "metadata.csv"
    metadata.parent.mkdir(parents=True)
    moore_audio = processed / "moore.wav"
    dioula_audio = processed / "dioula.wav"
    fulfulde_audio = processed / "fulfulde.wav"
    moore_audio.parent.mkdir(parents=True, exist_ok=True)
    for audio in [moore_audio, dioula_audio, fulfulde_audio]:
        audio.write_bytes(b"")

    with metadata.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=["chunk_audio", "language", "content_type", "chunk_id"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "chunk_audio": str(moore_audio),
                "language": "moore",
                "content_type": "contes",
                "chunk_id": "moore-contes-001",
            }
        )
        writer.writerow(
            {
                "chunk_audio": str(dioula_audio),
                "language": "dioula",
                "content_type": "contes",
                "chunk_id": "dioula-contes-001",
            }
        )
        writer.writerow(
            {
                "chunk_audio": str(fulfulde_audio),
                "language": "fulfulde",
                "content_type": "proverbes",
                "chunk_id": "fulfulde-proverbes-001",
            }
        )

    jobs = discover_segmentation_jobs(
        processed,
        languages={"moore", "dioula"},
        content_types={"contes"},
    )

    assert [job.audio_path for job in jobs] == [dioula_audio, moore_audio]
    assert [job.output_csv.name for job in jobs] == [
        "dioula-contes-001.segments.csv",
        "moore-contes-001.segments.csv",
    ]
