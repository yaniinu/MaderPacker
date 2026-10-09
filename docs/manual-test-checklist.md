# MaderPacker manual checklist

## GUI basics (Windows)
- [ ] `python -m maderpacker` opens the window (no console errors).
- [ ] First launch shows the intro (logo, MaderPacker, Created by
      yaniinuuu); Close dismisses it and it never auto-shows again;
      **About** reopens it, and the PH Corner link opens your profile
      in the browser.
- [ ] Add two folders → table lists rows from both; numbering collisions
      across folders show as rejected rows and in the orange warning line.
- [ ] Scanning shows the overlay: progress bar + live file count +
      current folder/file name; hides when the scan settles or fails.
- [ ] Each added path row has an ✕ — clicking it removes just that
      folder and rescans immediately.
- [ ] Drop a `Song - Singer.mid` (no number) in a folder → scan prompts
      「N files have no valid numbers… Assign now?」; Yes assigns the next
      free numbers (rows go green, warning shows `N auto-assigned`);
      Cancel leaves them for manual entry (Number column editable,
      duplicates/short values revert with a reason).
- [ ] Pack while unassigned files remain → the same prompt reappears
      before any folder dialog; Cancel aborts the pack.
- [ ] Pack → output folder picker; pick an empty folder →
      `<chosen>\idx\shubidx` + `shubblob` are created; status shows
      `N packed, M rejected → <chosen>`.
- [ ] Pack again into a folder whose `idx` already has a library →
      overwrite confirmation appears; No aborts, Yes overwrites.
- [ ] Open output folder reveals the `idx` folder.
- [ ] Duplicate-numbered files are rejected before packing.

## Library acceptance (device) — GATE
- [ ] BACK UP the vendor library dir (`...\SongHub\...\idx\`).
- [ ] Copy the packed pair into the vendor `idx\` folder (shubidx + shubblob).
- [ ] Launch the vendor player: catalog loads, titles/singers visible.
- [ ] Play at least 3 songs from the packed set + confirm audio.
- [ ] Restore the backup afterwards.

## Release
- [ ] `tools/build_exe.ps1` → `dist\MaderPacker.exe` starts and packs a folder.
      (If you force-kill it while testing, use `taskkill /F /T /IM MaderPacker.exe`
      — PyInstaller onefile runs as parent + child, so plain Stop-Process leaks
      the child and locks the exe for rebuilds.)
- [ ] `pyi-archive_viewer -l dist\MaderPacker.exe | Select-String "shubidx"`
      (archive uses backslash paths: `fixtures\shubidx`).
- [ ] `git remote -v` is empty; key-hygiene grep clean (see AGENTS.md).
