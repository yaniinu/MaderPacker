"""Strict input validation: NNNNNN - Title - Singer.mid or .kar (spec §4)."""
import re
from dataclasses import replace
from pathlib import Path

from maderpacker.model import ValidatedSong

NAME_RE = re.compile(r"(?i)^(\d{6}) - (.+) - (.+)\.(?:mid|kar)$")
MIDI_SUFFIXES = {".mid", ".kar"}
ENCODING = "cp1252"
MAX_TITLE_BYTES = 243
MAX_SINGER_BYTES = 250
MIDI_MAGIC = b"MThd"

SALVAGE_RE = re.compile(r"(?i)^(?:\d+ - )?(.+) - (.+)\.(?:mid|kar)$")


def salvage_name(filename: str) -> "tuple[str, str] | None":
    """Parse Title - Singer (optional wrong-length number prefix) or None."""
    m = SALVAGE_RE.match(filename)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_name(filename: str) -> tuple[str, str, str] | None:
    m = NAME_RE.match(filename)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _encodable(s: str) -> bool:
    try:
        s.encode(ENCODING)
        return True
    except UnicodeEncodeError:
        return False


def field_reason(title: str, singer: str) -> str:
    """Pure field checks; '' when both are acceptable."""
    if title != title.strip() or not title.strip():
        return "title has leading/trailing whitespace"
    if singer != singer.strip() or not singer.strip():
        return "singer has leading/trailing whitespace"
    if not _encodable(title):
        return f"title not encodable in {ENCODING}"
    if not _encodable(singer):
        return f"singer not encodable in {ENCODING}"
    if len(title.encode(ENCODING)) > MAX_TITLE_BYTES:
        return f"title too long (max {MAX_TITLE_BYTES} bytes)"
    if len(singer.encode(ENCODING)) > MAX_SINGER_BYTES:
        return f"singer too long (max {MAX_SINGER_BYTES} bytes)"
    return ""


def assign_numbers(rows: list[ValidatedSong]) -> list[ValidatedSong]:
    """Give every needs_number row the next free 6-digit number (pure)."""
    if not any(r.needs_number for r in rows):
        return list(rows)
    taken = {int(r.number) for r in rows if r.number}
    nxt = max(taken) + 1 if taken else 1
    out: list[ValidatedSong] = []
    for r in rows:
        if not r.needs_number:
            out.append(r)
            continue
        if nxt > 999999:
            out.append(replace(r, ok=False,
                               reason="no free 6-digit numbers",
                               needs_number=False))
        else:
            out.append(replace(r, number=f"{nxt:06d}", ok=True, reason="",
                               needs_number=False))
            nxt += 1
    return out


def overlap_summary(rows: list[ValidatedSong], auto_assigned: int = 0) -> str:
    """One-line warning text: duplicated numbers + this session's auto-assign count."""
    counts: dict[str, int] = {}
    for r in rows:
        if r.number:
            counts[r.number] = counts.get(r.number, 0) + 1
    dups = {n: c for n, c in counts.items() if c > 1}
    parts: list[str] = []
    if dups:
        parts.append("overlapping numbers: " + ", ".join(
            f"{n} ({c} files)" for n, c in sorted(dups.items())))
    if auto_assigned:
        parts.append(f"{auto_assigned} auto-assigned")
    return "; ".join(parts)


def scan_folder(folders: "Path | list[Path]", progress=None) -> list[ValidatedSong]:
    """Scan one folder or a list of folders; rows sorted (folder order, name).

    progress(done, total, note) is optional: called once per folder while
    listing (total=0) and once per file while validating (total=count).
    """
    if isinstance(folders, Path):
        folder_list = [folders]
    else:
        folder_list = list(folders)
    candidates: list[tuple[int, Path]] = []
    for fi, folder in enumerate(folder_list):
        if progress is not None:
            progress(0, 0, f"Listing {folder.name}…")
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in MIDI_SUFFIXES:
                candidates.append((fi, p))
    candidates.sort(key=lambda t: (t[0], t[1].name))
    parsed = [(fi, p, parse_name(p.name)) for fi, p in candidates]
    counts: dict[str, int] = {}
    for _, _, r in parsed:
        if r is not None:
            counts[r[0]] = counts.get(r[0], 0) + 1
    rows: list[ValidatedSong] = []
    total = len(parsed)
    for idx, (_, path, r) in enumerate(parsed):
        if progress is not None:
            progress(idx + 1, total, path.name)
        if r is None:
            salv = salvage_name(path.name)
            if salv is None:
                rows.append(ValidatedSong("", "", "", path, False,
                                          "filename must be NNNNNN - Title - Singer.mid or .kar (6 digits)"))
                continue
            title, singer = salv
            reason = field_reason(title, singer)
            if not reason:
                with open(path, "rb") as f:
                    if f.read(4) != MIDI_MAGIC:
                        reason = "not a MIDI file (missing MThd header)"
            if reason:
                rows.append(ValidatedSong("", title, singer, path, False, reason))
            else:
                rows.append(ValidatedSong("", title, singer, path, False,
                                          "needs number", needs_number=True))
            continue
        number, title, singer = r
        reason = ""
        if counts[number] > 1:
            reason = f"duplicate number {number} ({counts[number]} files)"
        else:
            reason = field_reason(title, singer)
            if not reason:
                with open(path, "rb") as f:
                    if f.read(4) != MIDI_MAGIC:
                        reason = "not a MIDI file (missing MThd header)"
        rows.append(ValidatedSong(number, title, singer, path, reason == "", reason))
    return rows
