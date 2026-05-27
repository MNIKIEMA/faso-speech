from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


def summarize_index(input_index: Path) -> list[dict[str, object]]:
    with input_index.open(newline="", encoding="utf-8") as input_file:
        rows = list(csv.DictReader(input_file))

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["catalog_id"]].append(row)

    summary = []
    for catalog_id, group in sorted(groups.items()):
        statuses = Counter(row["status"] for row in group)
        summary.append(
            {
                "catalog_id": catalog_id,
                "pages_archived": len(group),
                "audio_found": sum(row["has_audio"] == "True" for row in group),
                "timings_found": sum(row["has_timing"] == "True" for row in group),
                "statuses": dict(statuses),
            }
        )
    return summary
