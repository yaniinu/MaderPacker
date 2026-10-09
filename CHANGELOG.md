# Changelog

## [0.1.0] - 2026-10-09

### Added
- Strict validation of `NNNNNN - Title - Singer.mid`/`.kar` folders with
  per-file failure reasons (bad names, duplicate numbers, invalid MIDI,
  encoding problems)
- Fresh `shubidx` + `shubblob` packing (MKMD blocks, AES-256-CBC +
  raw deflate, 2048-sector aligned)
- Multi-folder scan with cross-folder duplicate-number detection
- Auto-assignment of missing numbers after a prompt, editable per row,
  overlap warnings, collision-free guarantees
- Mandatory output picker writing `<chosen>/idx/shubidx|shubblob`
- Review table with live Result preview, duplicate groups, dry-run mode
- First-launch intro and About dialog with logo
- Scan progress overlay with live file count and per-row folder removal
- Full-library round-trip verification tool (`tools/roundtrip_full.py`)
- Standalone Windows x64 exe (no Python required) with logo icon
