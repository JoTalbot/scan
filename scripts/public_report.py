#!/usr/bin/env python3
"""Generate a public-safe JSON report from newline-delimited findings."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from report_sanitize import public_finding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--salt", default="public-report-v1")
    args = parser.parse_args()

    findings = []
    with args.input.open(encoding="utf-8") as src:
        for line in src:
            if line.strip():
                findings.append(public_finding(json.loads(line), salt=args.salt))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"count": len(findings), "findings": findings}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
