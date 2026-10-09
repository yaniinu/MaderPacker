<p align="center">
  <img src="assets/logo.svg" width="150" alt="MaderPacker logo">
</p>

# MaderPacker

MaderPacker turns a folder of numbered karaoke MIDI files into a
SongHub-format library — the `shubidx` + `shubblob` pair the vendor
karaoke player loads.

Same filename convention (`NNNNNN - Title - Singer.mid`/`.kar`), same
container (MKMD blocks, AES-256-CBC + raw deflate, 2048-sector aligned),
same index layout as the vendor library.

## Input rules (strict)

- Every file must be named `NNNNNN - Title - Singer.mid`/`.kar` — exactly 6
  digits; last ` - ` segment is the singer, the rest is the title.
- Duplicate numbers are rejected before anything is packed.
- Several folders can be added at once (duplicates are checked across all
  of them). Names missing the number (`Title - Singer.mid`) can be
  auto-assigned after a prompt or edited manually — numbers never overlap.
- The output folder is chosen at pack time: MaderPacker creates
  `<chosen>/idx/` and writes `shubidx` + `shubblob` inside it.
- Files must be valid MIDI (`MThd` header) and their names must encode
  cleanly in the library's language encoding.

## Requirements

- Windows 10/11. No internet, no account, nothing leaves your machine.

## From source

```powershell
powershell -File tools/setup_env.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m maderpacker
```

## Important — personal use only

Only point MaderPacker at song libraries **you own**. The songs belong to
their copyright holders; do not upload, share, or distribute packed
libraries or extracted files. MaderPacker is an independent
interoperability tool, not affiliated with or endorsed by any karaoke
app vendor.

## Third-party components

- Icons: coolicons by Kryston Schwarze (CC BY 4.0).
- Interface fonts: DejaVu (bundled, see `maderpacker/fonts/LICENSE`).

## See also

- `docs/format-shubidx.md` — index format specification
- `docs/format-shubblob.md` — song container format specification
