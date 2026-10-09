"""Orchestrate a fresh pack: ok rows -> shubblob -> shubidx (spec §3, §5)."""
import pathlib
from dataclasses import dataclass
from typing import Callable, Optional

from maderpacker import idxwrite, pack
from maderpacker.model import PackedSong, ValidatedSong

Progress = Optional[Callable[[int, int], None]]


class BuildError(Exception):
    pass


@dataclass(frozen=True)
class BuildResult:
    packed: int
    rejected: int
    idx_path: pathlib.Path
    blob_path: pathlib.Path


def build_library(rows: list[ValidatedSong], out_dir: pathlib.Path,
                  progress: Progress = None) -> BuildResult:
    ok = [r for r in rows if r.ok]
    rejected = len(rows) - len(ok)
    if not ok:
        raise BuildError("no valid songs to pack")
    if len(ok) > 65535:
        raise BuildError(f"too many songs ({len(ok)}; max 65535)")
    order = sorted(ok, key=lambda r: (r.title.upper(), r.number))
    singers = sorted({r.singer for r in ok}, key=lambda s: (s.upper(), s))
    if len(singers) > 16383:
        raise BuildError(f"too many singers ({len(singers)}; max 16383)")
    idx_of = {name: i for i, name in enumerate(singers)}
    out_dir.mkdir(parents=True, exist_ok=True)
    blob_path = out_dir / "shubblob"
    idx_path = out_dir / "shubidx"
    packed: list[PackedSong] = []
    try:
        with open(blob_path, "wb") as f:
            pos = 0
            for done, row in enumerate(order, start=1):
                midi = row.path.read_bytes()
                if not midi.startswith(b"MThd"):
                    raise BuildError(f"not a MIDI file: {row.path.name}")
                block = pack.build_block(midi)
                f.write(block)
                sectors = len(block) // pack.SECTOR
                packed.append(PackedSong(row.number, row.title, idx_of[row.singer],
                                         pos, sectors))
                pos += sectors
                if progress is not None:
                    progress(done, len(order))
    except OSError as e:
        raise BuildError(str(e)) from e
    try:
        idx_bytes = idxwrite.write_index(idxwrite.load_template(), singers, packed)
        idx_path.write_bytes(idx_bytes)
    except (OSError, ValueError) as e:
        raise BuildError(str(e)) from e
    return BuildResult(len(order), rejected, idx_path, blob_path)
