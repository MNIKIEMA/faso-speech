from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


@contextmanager
def write_and_rename(
    path: Path,
    mode: str = "w",
    suffix: str = ".tmp",
    encoding: str | None = None,
    newline: str | None = None,
) -> Iterator[IO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(path) + suffix)
    try:
        with tmp_path.open(mode, encoding=encoding, newline=newline) as output_file:
            yield output_file
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
