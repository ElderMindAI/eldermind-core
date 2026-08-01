"""Re-freeze the golden files.

Run this ONLY when you have deliberately changed the engine and have checked
the resulting diff line by line. A golden file regenerated without reading the
diff is worse than no golden file at all: it turns a contract into a rubber
stamp.

    python tools/regenerate_golden.py            # show what would change
    python tools/regenerate_golden.py --write    # actually rewrite

After `--write`, `git diff tests/golden/expected/` is the change you are about
to ship to every paying client. Bump `ENGINE_VERSION` if any number moved.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.golden_support import (  # noqa: E402
    EXPECTED_DIR,
    compute_case,
    dump,
    expected_path,
    load_cases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the frozen files instead of only reporting differences",
    )
    args = parser.parse_args()

    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    changed: list[str] = []
    created: list[str] = []

    for case in load_cases():
        case_id = case["id"]
        payload = dump(compute_case(case))
        path = expected_path(case_id)

        if not path.exists():
            created.append(case_id)
        elif path.read_text(encoding="utf-8") != payload:
            changed.append(case_id)
        else:
            continue

        if args.write:
            path.write_text(payload, encoding="utf-8")

    verb = "Wrote" if args.write else "Would write"
    print(f"{verb} {len(created)} new, {len(changed)} changed, out of {len(load_cases())} cases.")
    for case_id in created:
        print(f"  new      {case_id}")
    for case_id in changed:
        print(f"  CHANGED  {case_id}")

    if changed and not args.write:
        print("\nEngine output moved. Read the diff before re-running with --write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
