"""Author a fresh shubidx: template slice + new singer/song/code records (spec §5)."""
import struct
import sys
from pathlib import Path

from maderpacker.idx_extract import detect_p_index_start
from maderpacker.model import PackedSong

_SRC_TEMPLATE = Path(__file__).resolve().parent.parent / "fixtures" / "shubidx"
ENCODING = "cp1252"
STYLE = 1
LANG = 0


def load_template() -> bytes:
    if _SRC_TEMPLATE.exists():
        return _SRC_TEMPLATE.read_bytes()
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "fixtures" / "shubidx"
        if p.exists():
            return p.read_bytes()
    raise FileNotFoundError("template shubidx not found (fixtures/shubidx)")


def template_slice(data: bytes) -> bytes:
    pos = detect_p_index_start(data)
    while pos < len(data) and data[pos] in (0x06, 0x07, 0x04):
        pos += data[pos + 1]
    return data[:pos]


def encode_code(number: str) -> bytes:
    code = int(number)
    return bytes([0x09, (code >> 16) & 0xFF, code & 0xFF, (code >> 8) & 0xFF])


def encode_singer(name: str, song_count: int) -> bytes:
    body = struct.pack("<HB", min(song_count, 4095), STYLE) + name.encode(ENCODING)
    return bytes([0x05, len(body) + 2]) + body


def encode_song(singer_idx: int, size_sectors: int, pos_sectors: int,
                title: str) -> bytes:
    if singer_idx > 0x3FFF:
        raise ValueError(f"singer index {singer_idx} exceeds 0x3FFF")
    if size_sectors > 0xFFFD:
        raise ValueError(f"block size {size_sectors} sectors exceeds 0xFFFD")
    fixed = struct.pack("<BBHHI", STYLE, LANG, singer_idx, size_sectors, pos_sectors)
    title_b = title.encode(ENCODING)
    ln = 12 + len(title_b)
    if ln > 255:
        raise ValueError(f"title too long for record ({ln} > 255)")
    return bytes([0x01, ln]) + fixed + title_b


def write_index(template: bytes, singers: list[str],
                songs: list[PackedSong]) -> bytes:
    if len(singers) > 16383:
        raise ValueError(f"too many singers ({len(singers)}; max 16383)")
    if len(songs) > 65535:
        raise ValueError(f"too many songs ({len(songs)}; max 65535)")
    buf = bytearray(template_slice(template))
    struct.pack_into("<H", buf, 28, len(singers))
    struct.pack_into("<H", buf, 30, len(songs))
    counts = [0] * len(singers)
    for s in songs:
        counts[s.singer_idx] += 1
    for i, name in enumerate(singers):
        buf += encode_singer(name, counts[i])
    for s in songs:
        buf += encode_song(s.singer_idx, s.midi_size, s.midi_pos, s.title)
    for s in songs:
        buf += encode_code(s.number)
    return bytes(buf)
