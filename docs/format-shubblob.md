# shubblob (MKMD container) Format Specification

Derived from `MegmidReader.java`, `NativeLib` (`libMewtwo.so` x86_64
disassembly with capstone) and validated by extracting all 6 ground-truth
songs to structurally valid Format-1 MIDI. All integers little-endian
unless noted.

## 1. Container layout (`idx/shubblob`, 606,828,544 bytes)

- A flat sequence of **48,000 blocks** (47,998 songs + 2 extra), each
  starting with magic `MKMD` (`4D 4B 4D 44`), each **2048-aligned**.
- Gaps between consecutive `MKMD` offsets are multiples of 2048
  (observed 2048–94208; most common 8192/10240/12288).
- A song's block: byte offset = `midiPosSectors × 2048`,
  byte length = `midiSizeSectors × 2048`
  (`MegSong.midiByteOffset/midiByteLength` use
  `PlaybackStateCompat.ACTION_PLAY_FROM_SEARCH = 2048`;
  single-file layout makes `resolveLocalOffset` the identity).
- The next `MKMD` starts exactly where the song's byte range ends
  (zero tail padding observed, e.g. `'Nyebe'` 9 sectors = 18432 bytes).

## 2. Song block layout

```text
0x00  "MKMD"                       magic
0x04  u8 version == 1              (native rejects anything else)
0x05  u32 A                        inflated MIDI byte length
0x09  u32 B                        raw-deflate input length
0x0D  AES-256-CBC ciphertext ...   (see §3)
```

Examples (`MKMD 01 A B`): `'Nyebe'` → A=52225, B=17055;
`'Pag Pwede…` → A=37534, B=18205;
`You're…(English Version)` → A=29394, B=13402.

## 3. Decryption (`NativeLib.processMidiData`, `libMewtwo.so`)

Reference: `MegmidReader.readMidi` slices `[off, off+len)` then calls
`processMidiData(bytes, bypass)`; `bypass` only matters for non-`MKMD`
input (plain `MThd` passthrough), so the song path always decrypts.

1. Require magic `MKMD`, version `1`, total length ≥ 13.
2. `declen = min(align16(len − 13), align16(B) + 16)` bytes of ciphertext
   at `+13` (for B≢0 mod 16 this equals `align16(B)`; the `+16` covers
   the B≡0 case with one spare block).
3. **AES-256-CBC decrypt** with the vendor key/IV (kept in
   `maderpacker/crypto.py` — never reproduced in docs; recovered from
   `libMewtwo.so` `.rodata` via rip-relative `movaps` loads in
   `processMidiData`, with 32-byte key expansion confirmed in
   `AES_init_ctx_iv`).
4. Require at least B decrypted bytes, then **raw-inflate**
   (`inflateInit2(-15)`, i.e. zlib without header) the first B bytes.
   Result is exactly A bytes starting with `MThd`.

Python equivalent (needs an AES lib, e.g. pycryptodome;
`KEY`/`IV` imported from `maderpacker.crypto`):

```python
ct = block[13:13 + declen]
pt = AES.new(KEY, AES.MODE_CBC, IV).decrypt(ct)
midi = zlib.decompress(pt[:B], wbits=-15)  # len(midi) == A, starts with b"MThd"
```

## 4. Validation

All 6 `ground_truth.csv` songs decrypt + inflate to well-formed MIDI:
`MThd` header, format 1, every `MTrk` chunk length-checked to EOF byte.
(`'Nyebe'`: 32 tracks, 52,225 bytes; full table in investigation notes.)

## 5. Notes / open questions

- Known-bad entry: song `031872` (`Home`, Mike Posner) decrypts and
  inflates correctly (13,494 bytes) but the payload is not a valid MIDI
  (headerless track body + one valid `MTrk` + corrupt trailing section).
  The Android app itself reports "not a valid midi file" for it, so the
  exporter skips it — matching reference behavior. Final yield:
  47,997 / 47,998 songs.

- The 2 non-song `MKMD` blocks (48,000 blocks vs 47,998 songs) are
  unidentified (one is at file offset 0) — likely container/global headers.
- `MegvolReader` (MP3 songs, `megvol` files) uses raw slices with no
  native transform; this library has no mp3 songs, so that path is
  untested.
- `verifyDiagnosticPassword` in `NativeLib` was not investigated.
- Karaoke events/lyrics live inside the MIDI (player concern, out of scope
  for the catalog; next step toward Option B playback).
