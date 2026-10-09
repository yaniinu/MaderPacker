# shubidx Format Specification

Derived from `com.songhub.android.database.MegidxDatabase` (jadx output) and
validated byte-for-byte against `idx/shubidx`. All integers little-endian.
See `analysis/apk-findings.md` for the APK evidence.

## 1. File map (`idx/shubidx`, 1,797,052 bytes)

| Region | Offsets | Purpose |
|---|---|---|
| Legacy header | `0–55` | Counts + section pointers (§2) |
| Padding | `56–8607` | `0x00` (skipped by the walk) |
| Index | `8608–EOF` | Interleaved typed records (§3): languages, styles, singers (alphabetical), songs, 4-byte codes |

The parser walks the index from `pIndexStart` to EOF; record boundaries come
from each record's own length byte. There are no separate section offsets —
`pSingerPos/pSongPos/pNumIndexPos` are unused by the catalog path.

Observed census: 15 × `0x07`, 17 × `0x04`, 6 × `0x06` (ignored),
15,795 × `0x05`, 47,998 × `0x01`, 47,998 × `0x09`.

## 2. Legacy header

Detection: `u32@52 (8608) > u32@24 (8478)`, byte@8608 = `6` (valid start),
u32@56 out of range → legacy (`parseLegacyHeader`).

| Offset | Size | Field | Value in our file |
|---|---|---|---|
| 0 | u32 | pSingerType | 0 |
| 4 | u32 | pLanguageType | 55 |
| 8 | u32 | pSongType | 207 |
| 12 | u32 | pSingerCode | 389 |
| 16 | u32 | pSongInfo | 317841 |
| 20 | u32 | pSongWord | 8348 |
| 24 | u32 | pSingerWord | 8478 |
| 28 | u16 | singerNum | 15795 |
| 30 | u16 | songNum | 47998 |
| 32 | u16 | songWordNum | (unused by catalog) |
| 34 | u16 | singerWordNum | (unused by catalog) |
| 36 | u16 | songNameNumFlag | (unused by catalog) |
| 38 | u16 | singerNameNumFlag | (unused by catalog) |
| 40 | u32 | pSingerPos | (unused by catalog) |
| 44 | u32 | pSongPos | (unused by catalog) |
| 48 | u32 | pNumIndexPos | (unused by catalog) |
| 52 | u32 | pIndexStart | **8608** |

(An extended 60-byte header variant exists in the code for other files;
this file is legacy. A robust reader implements the same detection rule.)

First 8 u32 fixture: `[0, 55, 207, 389, 317841, 8348, 8478, 0xBB7E3DB3]`.

## 3. Index record framing

```text
u8 type | u8 len | <len-2 payload bytes>
```

- `len < 2` or `pos+len > filesize` → stop walk.
- `type == 0x00` → advance 1 byte (padding), not a record.
- `type == 0x09` → exactly 4 bytes (`09 b1 b2 b3`), a song code (§6).

## 4. Title (song) record — type `0x01`

```text
01 <len> <style:u8> <lang:u8> <singerIdx:u16> <midiSize:u16> <midiPos:u32>
<title bytes…> [<singerIdx:u32> if u16 == 0xFFFF]
[<midiSize:u32> if u16 == 0xFFFE] [mp3 tail if langType == 2 …]
```

- `lang = u8`: bit7 set → mp3 song (`langType=2`), low 7 bits = `langId`
  (index into the language list). Otherwise `langType=1`.
- `singerIdx = u16 & 0x3FFF` → index into the singer list (§5).
- Name starts at `pos+12` (`pos+18` for mp3, which additionally carry
  `mp3Vol/mp3Pos` u32 at `+12` and `mp3Size` u16 at `+16`,
  `0xFFFE` → u32 tail). Name length = `len − 2 − fixed − tails`
  (`fixed` = 10, or 16 for mp3).
- Name decoded with `encodings[langId]`, fallback `ISO-8859-1`;
  strip `\x00`, trim. Encoding per language name per
  `LanguageEncoding.getEncodingForLanguage` (e.g. Chinese→GBK,
  Japanese→Shift_JIS, Korean→EUC-KR, default→CP1252, Vietnam→ISO-8859-1).
- `midiSize/midiPos` are sector counts into `shubblob` (playback only).
- This library contains no mp3 (`langType == 2`) songs.

Known fixtures (offset = record start):

| title | offset | header bytes | singerIdx | midiPos |
|---|---|---|---|---|
| `'Nyebe'` | 326897 | `01 13 01 00` | `0x323E`=12862 | `0x0001A3FE`=107518 |
| `'Pag Pwede Na Ang Puso Mo` | 326916 | `01 25 01 00` | `0x38FD`=14589 | `0x00010248`=66120 |
| `Summoning Eru` | 1371264 | `01 19 01 00` | 7513 | 106042 |
| `You're My Everything(English Version)` | 1596390 | `01 31 01 00` | 5652 | 174300 |

Note: each record's 12 header bytes sit *before* its own title — the old
CSV's `metadata_hex` column captured the *following* record's header.

## 5. Singer resolution

Singer record — type `0x05`:

```text
05 <len> <packed:u16> <style:u8> <name bytes…>   (name length = len−5)
packed: number = (packed>>12)&15 ; count = packed&4095 (both informational)
```

- Song → singer: `singers[song.singerIdx].name`; `""` if out of range.
- Singer *i* (list order) is decoded with the encoding of songs with
  `singerIdx == i`, else the first language's encoding, else ISO-8859-1.
- `Gummy` sits at file offset 124123 in this table.

## 6. songNum resolution

- The *k-th* type-`0x09` block in the walk assigns `songs[k].code`
  (both lists in file order; first `min(len)` pairs).
- Block `09 b1 b2 b3` → `code = (b1<<16) | (b3<<8) | b2`.
- Displayed number = `f"{code:06d}"` (cf. `"%06d"` in `SongListActivity`).

Verified: 47,998 songs ↔ 47,998 codes; the 4 reference songs resolve exactly.

## 7. Open questions (non-blocking)

- Type-`0x06` records: skipped by the APK parser; purpose unknown.
- Singer `number`/`count` nibble fields: meaning unknown, unused.
- Extended-header files: same detection rule applies; untested (no sample).
