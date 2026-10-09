"""SongHub .shubidx catalog extractor.

Reads a SongHub index file (as parsed by com.songhub.android.database.MegidxDatabase)
and exports Number | Title | Singer rows. See docs/format-shubidx.md.
Standard library only.
"""
import struct
import sys
from dataclasses import dataclass
from typing import Iterator

IDX_SENTINEL_U16 = 0xFFFF  # extended u32 follows the name
SIZE_SENTINEL_U16 = 0xFFFE  # extended u32 follows the name


class IdxFormatError(Exception):
    def __init__(self, msg: str, offset: int | None = None):
        super().__init__(f"{msg} (offset {offset})" if offset is not None else msg)
        self.offset = offset


HEADER_U32_COUNT = 14


def read_header(data: bytes) -> dict[int, int]:
    if len(data) < HEADER_U32_COUNT * 4:
        raise IdxFormatError("file too small for header")
    return dict(enumerate(struct.unpack_from(f"<{HEADER_U32_COUNT}I", data, 0)))


@dataclass(frozen=True)
class SongRecord:
    title: str
    style: int
    lang_id: int
    lang_type: int
    singer_idx: int
    midi_size: int
    midi_pos: int
    offset: int
    length: int


def parse_record_at(data: bytes, offset: int) -> tuple[SongRecord, int]:
    """Parse one type-0x01 song record at record offset; return (record, next offset)."""
    if offset + 12 > len(data) or data[offset] != 0x01:
        raise IdxFormatError("not a song record", offset)
    ln = data[offset + 1]
    if ln < 12 or offset + ln > len(data):
        raise IdxFormatError("bad song record length", offset)
    style = data[offset + 2]
    lang = data[offset + 3]
    lang_type = 2 if (lang & 0x80) else 1
    lang_id = lang & 0x7F
    singer_raw = struct.unpack_from("<H", data, offset + 4)[0]
    singer_idx = singer_raw & 0x3FFF
    is_idx_ext = singer_raw == IDX_SENTINEL_U16
    midi_size = struct.unpack_from("<H", data, offset + 6)[0]
    midi_pos = struct.unpack_from("<I", data, offset + 8)[0]
    if lang_type == 2:
        mp3_size = struct.unpack_from("<H", data, offset + 16)[0]
        extra = (4 if midi_size == SIZE_SENTINEL_U16 else 0) + (4 if mp3_size == SIZE_SENTINEL_U16 else 0)
        name_len = max(0, (ln - 2) - 16 - extra)
        title = data[offset + 18:offset + 18 + name_len].decode("ascii")
        q = offset + 18 + name_len
    else:
        extra = (4 if is_idx_ext else 0) + (4 if midi_size == SIZE_SENTINEL_U16 else 0)
        name_len = max(0, (ln - 2) - 10 - extra)
        title = data[offset + 12:offset + 12 + name_len].decode("ascii")
        q = offset + 12 + name_len
    if is_idx_ext:
        singer_idx = struct.unpack_from("<I", data, q)[0]
        q += 4
    if midi_size == SIZE_SENTINEL_U16:
        midi_size = struct.unpack_from("<I", data, q)[0]
    return (SongRecord(title, style, lang_id, lang_type, singer_idx,
                       midi_size, midi_pos, offset, ln), offset + ln)


def iter_records(data: bytes, start: int, end: int) -> Iterator[SongRecord]:
    pos = start
    while pos < end:
        rec, pos = parse_record_at(data, pos)
        yield rec


DEFAULT_ENCODING = "ISO-8859-1"
_VALID_STARTS = (1, 2, 3, 4, 5, 6, 7, 9)


def _is_valid_index_start(data: bytes, pos: int) -> bool:
    return 0 < pos < len(data) and data[pos] in _VALID_STARTS


def detect_p_index_start(data: bytes) -> int:
    """Header detection mirroring MegidxDatabase.parse().

    Returns pIndexStart; raises IdxFormatError when the layout is unknown.
    """
    n = len(data)
    if n < 60:
        raise IdxFormatError("file too short for header")
    at24 = struct.unpack_from("<I", data, 24)[0]
    at52 = struct.unpack_from("<I", data, 52)[0]
    at56 = struct.unpack_from("<I", data, 56)[0]
    legacy = (at52 > at24 and _is_valid_index_start(data, at52)) and not (
        at56 > at24 and _is_valid_index_start(data, at56)
    )
    start = at52 if legacy else at56
    if not _is_valid_index_start(data, start):
        raise IdxFormatError("unknown header layout", 0)
    return start


def _decode(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding).replace("\x00", "").strip()
    except Exception:
        return raw.decode("latin-1").replace("\x00", "").strip()


def _encoding_for_language(name: str) -> str:
    """Port of LanguageEncoding.getEncodingForLanguage."""
    s = (name or "").lower().strip()
    if any(k in s for k in ("korean u", "china u", "japan u", "vietnam u", "taiwan u", "user midi")):
        return "utf-8"
    if any(k in s for k in ("chinese", "china", "mandarin", "cantonese")):
        return "gbk"
    if "korea" in s:
        return "euc-kr"
    if "japan" in s:
        return "shift_jis"
    if any(k in s for k in ("taiwan", "hongkong")):
        return "big5"
    if "russian" in s:
        return "cp1251"
    return "ISO-8859-1" if "vietnam" in s else "cp1252"


def _walk_index(data: bytes):
    """Full index walk. Returns (languages, styles, singers_raw, songs, codes).

    singers_raw: list of (number, count, style, name_bytes).
    songs: list of SongRecord with decoded titles (no codes yet).
    codes: list of int in file order.
    """
    n = len(data)
    start = detect_p_index_start(data)
    # Pass 1: languages + styles.
    languages: list[str] = []
    styles: dict[int, str] = {}
    pos = start
    while pos < n:
        t = data[pos]
        if t == 0:
            pos += 1
            continue
        if pos + 2 > n:
            break
        ln = data[pos + 1]
        if ln < 2 or pos + ln > n:
            break
        if t == 7:
            languages.append(_decode(data[pos + 4:pos + ln], DEFAULT_ENCODING))
        elif t == 4:
            styles[data[pos + 2]] = _decode(data[pos + 5:pos + ln], DEFAULT_ENCODING)
        pos += ln
    encodings = [_encoding_for_language(L) for L in languages]
    # Pass 2: singers + songs (codes skipped here, collected in pass 3).
    singers_raw: list[tuple[int, int, int, bytes]] = []
    songs: list[SongRecord] = []
    singer_enc: dict[int, str] = {}
    pos = start
    while pos < n:
        t = data[pos]
        if t == 0:
            pos += 1
            continue
        if t == 9:
            pos += 4
            continue
        if pos + 2 > n:
            break
        ln = data[pos + 1]
        if ln < 2 or pos + ln > n:
            break
        if t == 5:
            packed = struct.unpack_from("<H", data, pos + 2)[0]
            singers_raw.append(((packed >> 12) & 15, packed & 4095,
                                data[pos + 4], data[pos + 5:pos + ln]))
        elif t == 1:
            songs.append(_parse_song_block(data, pos, ln, encodings))
            rec = songs[-1]
            singer_enc[rec.singer_idx] = (
                encodings[rec.lang_id] if 0 <= rec.lang_id < len(encodings) else DEFAULT_ENCODING
            )
        pos += ln
    # Pass 3: codes in file order.
    codes: list[int] = []
    pos = start
    while pos < n:
        if data[pos] == 9:
            j5 = struct.unpack_from("<I", data, pos)[0]
            codes.append(((j5 >> 16) & 0xFFFF) | ((j5 & 0xFF00) << 8))
            pos += 4
        else:
            if pos + 2 > n:
                break
            ln = data[pos + 1]
            pos = pos + 1 if ln < 2 else pos + ln
    return languages, styles, singers_raw, songs, codes, singer_enc, encodings


def _parse_song_block(data: bytes, pos: int, ln: int, encodings: list[str]) -> SongRecord:
    """Port of MegidxDatabase.parseSongBlock (title decoding included)."""
    style = data[pos + 2]
    lang = data[pos + 3]
    lang_type = 2 if (lang & 0x80) else 1
    lang_id = lang & 0x7F
    singer_raw = struct.unpack_from("<H", data, pos + 4)[0]
    singer_idx = singer_raw & 0x3FFF
    is_idx_ext = singer_raw == IDX_SENTINEL_U16
    midi_size = struct.unpack_from("<H", data, pos + 6)[0]
    midi_pos = struct.unpack_from("<I", data, pos + 8)[0]
    enc = encodings[lang_id] if 0 <= lang_id < len(encodings) else DEFAULT_ENCODING
    p = pos + 12
    if lang_type == 2:
        mp3_size = struct.unpack_from("<H", data, pos + 16)[0]
        extra = (4 if midi_size == SIZE_SENTINEL_U16 else 0) + (4 if mp3_size == SIZE_SENTINEL_U16 else 0)
        name_len = max(0, (ln - 2) - 16 - extra)
        title = _decode(data[pos + 18:pos + 18 + name_len], enc)
        q = pos + 18 + name_len
    else:
        extra = (4 if is_idx_ext else 0) + (4 if midi_size == SIZE_SENTINEL_U16 else 0)
        name_len = max(0, (ln - 2) - 10 - extra)
        title = _decode(data[pos + 12:pos + 12 + name_len], enc)
        q = pos + 12 + name_len
    if is_idx_ext:
        singer_idx = struct.unpack_from("<I", data, q)[0]
        q += 4
    if midi_size == SIZE_SENTINEL_U16:
        midi_size = struct.unpack_from("<I", data, q)[0]
    return SongRecord(title, style, lang_id, lang_type, singer_idx,
                      midi_size, midi_pos, pos, ln)


def parse_titles(data: bytes) -> list[SongRecord]:
    """All songs in file order with decoded titles."""
    _, _, _, songs, _, _, _ = _walk_index(data)
    return songs


@dataclass(frozen=True)
class Tables:
    songs: list[SongRecord]
    singers: list[str]
    code_by_offset: dict[int, int]


def load_tables(data: bytes) -> Tables:
    """Full index load: decoded singers + song codes assigned in file order."""
    _, _, singers_raw, songs, codes, singer_enc, encodings = _walk_index(data)
    fallback = encodings[0] if encodings else DEFAULT_ENCODING
    singers = [_decode(raw, singer_enc.get(i, fallback))
               for i, (_, _, _, raw) in enumerate(singers_raw)]
    code_by_offset = {rec.offset: code for rec, code in zip(songs, codes)}
    return Tables(songs, singers, code_by_offset)


def resolve_number(rec: SongRecord, tables: Tables) -> str:
    """Displayed 6-digit song number for a record."""
    return f"{tables.code_by_offset[rec.offset]:06d}"


def resolve_singer(rec: SongRecord, tables: Tables) -> str:
    """Singer name for a record ("" when the index is out of range)."""
    if 0 <= rec.singer_idx < len(tables.singers):
        return tables.singers[rec.singer_idx]
    return ""


def extract_rows(data: bytes) -> list[tuple[str, str, str]]:
    """(number, title, singer) for every song in file order."""
    tables = load_tables(data)
    return [(resolve_number(rec, tables), rec.title, resolve_singer(rec, tables))
            for rec in tables.songs]


def main(argv: list[str]) -> int:
    import argparse
    import csv
    parser = argparse.ArgumentParser(description="Extract Number|Title|Singer catalog from a SongHub .shubidx file.")
    parser.add_argument("input", help="input .shubidx file")
    parser.add_argument("-o", "--output", default="songs.csv", help="output CSV path (default: songs.csv)")
    args = parser.parse_args(argv[1:])
    try:
        with open(args.input, "rb") as f:
            data = f.read()
        rows = extract_rows(data)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except IdxFormatError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["number", "title", "singer"])
        writer.writerows(rows)
    print(f"wrote {len(rows)} songs to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
