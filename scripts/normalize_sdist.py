#!/usr/bin/env python3
"""Canonicalize sdist archive metadata for byte-for-byte reproducibility."""

from __future__ import annotations

import argparse
import copy
import gzip
import os
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

ArchiveEntry = Tuple[tarfile.TarInfo, Optional[bytes]]


def normalize_sdist(path: Path, epoch: int) -> None:
    entries: List[ArchiveEntry] = []
    with tarfile.open(path, "r:gz") as archive:
        for original in archive.getmembers():
            member = copy.copy(original)
            extracted = archive.extractfile(original) if original.isfile() else None
            data = extracted.read() if extracted is not None else None
            member.mtime = epoch
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.pax_headers = {}
            entries.append((member, data))

    entries.sort(key=lambda entry: entry[0].name)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", dir=path.parent, delete=False
        ) as raw_output:
            temporary = Path(raw_output.name)
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw_output, mtime=epoch
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
                ) as output:
                    for member, data in entries:
                        if data is None:
                            output.addfile(member)
                        else:
                            output.addfile(member, BytesIO(data))
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sdist", type=Path)
    parser.add_argument(
        "--epoch",
        type=int,
        default=int(os.environ.get("SOURCE_DATE_EPOCH", "0")),
    )
    args = parser.parse_args()
    if args.epoch <= 0:
        parser.error("set SOURCE_DATE_EPOCH or pass a positive --epoch")
    normalize_sdist(args.sdist, args.epoch)
    print(f"Normalized reproducible metadata in {args.sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
