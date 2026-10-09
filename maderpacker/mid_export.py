"""Library MIDI exporter: index + song container -> numbered .mid files.

Output naming follows the PC karaoke app's "User Library Content Database"
convention:
    NNNNNN - Title - Singer.mid
so the app keeps each file's original number in N (keep-numbers) scan mode.

Requires pycryptodome (pip install pycryptodome) for AES-256-CBC.
See docs/format-shubblob.md.
"""
import struct
import sys
import zlib
from pathlib import Path

from maderpacker.crypto import MIDI_IV, MIDI_KEY
from maderpacker.idx_extract import IdxFormatError, load_tables, resolve_number, resolve_singer

SECTOR = 2048
MKMD_MAGIC = b"MKMD"
MKMD_VERSION = 1

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

_ILLEGAL = '<>:"/\\|?*'


class MidiError(Exception):
    pass


def sanitize_filename(name: str) -> str:
    cleaned = "".join("_" if (c in _ILLEGAL or ord(c) < 32) else c for c in name)
    return cleaned.strip().rstrip(".")


def song_filename(number: str, title: str, singer: str) -> str:
    return f"{sanitize_filename(number)} - {sanitize_filename(title)} - {sanitize_filename(singer)}.mid"


def _align16(n: int) -> int:
    return (n + 15) & ~15


def extract_midi(blob: bytes, pos_sectors: int, size_sectors: int) -> bytes:
    """Decrypt + inflate one song block to standard MIDI bytes."""
    if AES is None:
        raise MidiError("pycryptodome is required: pip install pycryptodome")
    off = pos_sectors * SECTOR
    total = size_sectors * SECTOR
    if off < 0 or off + total > len(blob):
        raise MidiError(f"song block out of range (offset {off}, length {total})")
    block = blob[off:off + total]
    if block[:4] != MKMD_MAGIC:
        raise MidiError(f"bad MKMD magic at offset {off}")
    if block[4] != MKMD_VERSION:
        raise MidiError(f"unsupported MKMD version {block[4]} at offset {off}")
    inflated_len, compressed_len = struct.unpack_from("<II", block, 5)
    declen = min((total - 13) & ~15, (compressed_len & ~15) + 16)
    plaintext = AES.new(MIDI_KEY, AES.MODE_CBC, MIDI_IV).decrypt(block[13:13 + declen])
    try:
        midi = zlib.decompress(plaintext[:compressed_len], wbits=-15)
    except zlib.error as e:
        raise MidiError(f"inflate failed at offset {off}: {e}")
    if not midi.startswith(b"MThd"):
        raise MidiError(f"decrypted data is not MIDI at offset {off}")
    if len(midi) != inflated_len:
        raise MidiError(f"MIDI length {len(midi)} != header {inflated_len} at offset {off}")
    return midi


def export_songs(idx_path: str, blob_path: str, out_dir: str, limit: int | None = None) -> list[tuple[str, str]]:
    """Export songs to out_dir. Returns [(number, filename)]."""
    idx_data = Path(idx_path).read_bytes()
    blob_data = Path(blob_path).read_bytes()
    try:
        tables = load_tables(idx_data)
    except IdxFormatError as e:
        raise MidiError(f"bad index file: {e}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    done: list[tuple[str, str]] = []
    errors = 0
    songs = tables.songs if limit is None else tables.songs[:limit]
    for rec in songs:
        number = resolve_number(rec, tables)
        singer = resolve_singer(rec, tables)
        name = song_filename(number, rec.title, singer)
        try:
            midi = extract_midi(blob_data, rec.midi_pos, rec.midi_size)
        except MidiError as e:
            print(f"skip {number} {rec.title}: {e}", file=sys.stderr)
            errors += 1
            continue
        (out / name).write_bytes(midi)
        done.append((number, name))
    print(f"exported {len(done)} songs to {out} ({errors} skipped)")
    return done


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Export SongHub library songs to numbered .mid files.")
    parser.add_argument("idx", help="input .shubidx file")
    parser.add_argument("blob", help="shubblob container file")
    parser.add_argument("outdir", help="output folder for .mid files")
    parser.add_argument("--limit", type=int, default=None, help="export first N songs only (test runs)")
    args = parser.parse_args(argv[1:])
    try:
        export_songs(args.idx, args.blob, args.outdir, args.limit)
    except (OSError, MidiError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
