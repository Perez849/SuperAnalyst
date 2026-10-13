#!/usr/bin/env python3
"""Refresh the vendored Reloj de inversión snapshot (equityval/data/reloj_snapshot.json).

Reports fetch the live data.json when the network allows and fall back to this snapshot, so
a fresh snapshot keeps offline / CI-without-network runs close to the live cycle reading.

    python scripts/refresh_reloj.py                       # fetch from GitHub Pages / raw
    python scripts/refresh_reloj.py --from /path/to/data.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from equityval import clockdata  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=None, help="local data.json (default: fetch live)")
    args = ap.parse_args()
    full = None
    if args.src:
        full = json.loads(Path(args.src).read_text(encoding="utf-8"))
    else:
        for url in (clockdata.PAGES_URL, clockdata.RAW_URL):
            full = clockdata._fetch(url, timeout=20)
            if full:
                break
    if not full or not full.get("current"):
        print("Could not read the Reloj data.json", file=sys.stderr)
        return 1
    snap = clockdata.trim(full)
    clockdata.SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    clockdata.SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    c = snap["current"]
    print(f"snapshot written: {clockdata.SNAPSHOT} ({clockdata.SNAPSHOT.stat().st_size/1024:.0f} KB) "
          f"| phase {c['phase']} ({c['date']}), confidence {c['call_strength']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
