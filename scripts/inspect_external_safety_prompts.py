#!/usr/bin/env python3
"""Inspect external safety prompt sources without printing raw prompt text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.prompts.safety_external import (
    SAFETY_PROMPT_ROOT_ENV,
    inventory_safety_prompt_root,
    iter_safety_prompt_records,
    resolve_safety_prompt_root,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, help=f"defaults to ${SAFETY_PROMPT_ROOT_ENV}")
    parser.add_argument("--limit", type=int, default=5, help="redacted sample metadata count")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = resolve_safety_prompt_root(args.root)
        inventory = inventory_safety_prompt_root(root)
        samples = iter_safety_prompt_records(root, include_text=False, limit=args.limit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "inventory": inventory.to_redacted_dict(),
        "samples": [record.to_redacted_dict() for record in samples],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"safety_prompt_root={root}")
        print(f"jsonl_files={inventory.file_count}")
        print(f"prompt_records={inventory.prompt_record_count}")
        print(f"unsupported_records={inventory.unsupported_record_count}")
        print("raw_prompt_text_printed=no")
        print("sample_records_redacted=" + json.dumps(payload["samples"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
