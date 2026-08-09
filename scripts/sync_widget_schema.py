#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Running this file directly sets sys.path to scripts/, not the repository root.
# Add the root explicitly so GitHub Actions can import the app package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.widget_schema_sync import fetch_official_widget_schemas


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Homepage official Widget Schema snapshot")
    parser.add_argument("--output", default="app/bundled_widget_schema.json")
    parser.add_argument("--ref", default="dev")
    args = parser.parse_args()
    widgets, meta = fetch_official_widget_schemas(ref=args.ref, timeout=12.0, workers=12)
    if len(widgets) < 50:
        raise SystemExit(f"refusing to write suspiciously small widget catalog: {len(widgets)}")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "meta": meta, "widgets": widgets}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(widgets)} widgets to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
