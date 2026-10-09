"""MKMD block builder: midi bytes -> sector-aligned encrypted block (spec §5)."""
import struct
import zlib

from Crypto.Cipher import AES

from maderpacker.crypto import MIDI_IV, MIDI_KEY

SECTOR = 2048
MKMD_MAGIC = b"MKMD"
MKMD_VERSION = 1


def align16(n: int) -> int:
    return (n + 15) & ~15


def raw_deflate(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def build_block(midi: bytes) -> bytes:
    comp = raw_deflate(midi)
    padded = comp + b"\x00" * ((-len(comp)) % 16)
    ct = AES.new(MIDI_KEY, AES.MODE_CBC, MIDI_IV).encrypt(padded)
    block = (MKMD_MAGIC + bytes([MKMD_VERSION])
             + struct.pack("<II", len(midi), len(comp)) + ct)
    return block + b"\x00" * ((-len(block)) % SECTOR)
