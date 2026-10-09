"""Heavy round-trip: export fixture library -> rebuild -> verify. Manual runs only.

Usage:
    .venv\\Scripts\\python.exe tools\\roundtrip_full.py            # full 47,998 songs
    .venv\\Scripts\\python.exe tools\\roundtrip_full.py --sample 500
Needs fixtures/shubidx + fixtures/shubblob and ~1.5 GB free TEMP space.
"""
import argparse
import collections
import pathlib
import shutil
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.build import build_library
from maderpacker.idx_extract import extract_rows, load_tables, resolve_number
from maderpacker.mid_export import export_songs, extract_midi
from maderpacker.validate import field_reason, parse_name, scan_folder
from tests.paths import IDX, BLOB


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None,
                    help="export/rebuild only the first N songs")
    args = ap.parse_args()
    if not BLOB.exists():
        print("FAIL: fixtures/shubblob missing")
        return 2
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="maderpacker_rt_"))
    t0 = time.time()
    try:
        src = tmp / "export"
        print(f"[1/4] exporting {args.sample or 'all'} songs ...")
        done = export_songs(str(IDX), str(BLOB), str(src), limit=args.sample)
        # Strict validation rejects some vendor-library rows by design:
        # empty singers export as "NNNNNN - Title - .mid", plus a few rows
        # whose bytes do not re-encode to cp1252. want = rows that SHOULD
        # survive validation; anything else is counted and expected rejected.
        reasons = collections.Counter()
        want = set()
        for _, filename in done:
            p = parse_name(filename)
            if p is None:
                reasons["bad filename"] += 1
                continue
            r = field_reason(p[1], p[2])
            if r:
                reasons[r] += 1
                continue
            want.add(p)
        print(f"[2/4] scanning + rebuilding {len(want)} songs "
              f"({sum(reasons.values())} strict-rejected: {dict(reasons)})")
        rows = scan_folder(src)
        bad = [r for r in rows if not r.ok]
        if len(bad) != sum(reasons.values()):
            print(f"FAIL: scan rejected {len(bad)} files, expected "
                  f"{sum(reasons.values())}: {bad[0] if bad else 'none'}")
            return 1
        result = build_library(rows, tmp / "out")
        print(f"      packed={result.packed} rejected={result.rejected}")
        print("[3/4] comparing row sets ...")
        got = set(extract_rows(result.idx_path.read_bytes()))
        if got != want:
            missing = list(want - got)[:3]
            extra = list(got - want)[:3]
            print(f"FAIL: row sets differ: missing={missing} extra={extra}")
            return 1
        print(f"[4/4] comparing MIDI bytes for {len(got)} songs ...")
        out_blob = result.blob_path.read_bytes()
        out_tables = load_tables(result.idx_path.read_bytes())
        by_code = {resolve_number(r, out_tables): r for r in out_tables.songs}
        file_by_number = dict(done)
        for i, (number, title, singer) in enumerate(sorted(want), start=1):
            rec = by_code[number]
            rebuilt = extract_midi(out_blob, rec.midi_pos, rec.midi_size)
            orig = (src / file_by_number[number]).read_bytes()
            if rebuilt != orig:
                print(f"FAIL: MIDI differs for {number} {title!r}")
                return 1
            if i % 5000 == 0:
                print(f"      {i}/{len(want)} verified")
        print(f"PASS: {len(want)} songs round-tripped in {time.time() - t0:.0f}s")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
