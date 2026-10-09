"""Shared row types."""
import pathlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidatedSong:
    number: str
    title: str
    singer: str
    path: pathlib.Path
    ok: bool
    reason: str  # "" when ok
    needs_number: bool = False  # salvageable name awaiting auto/manual number


@dataclass(frozen=True)
class PackedSong:
    number: str
    title: str
    singer_idx: int
    midi_pos: int   # sectors into shubblob
    midi_size: int  # block size in sectors
