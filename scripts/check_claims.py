"""Quality gate: every figure in the documents must match what the code produces.

Checks
1. results.json is reproducible: re-running the analysis from data/processed gives identical numbers.
2. README / memo / CV bullets / case_selection on disk equal a fresh render from the templates + results.json.
3. Templates contain no hand-typed decimals (all numbers come through placeholders).
4. Narrative assumptions (e.g. "composite did not beat the baseline") still hold for the current results.
Exit status 1 on any failure.
"""

from __future__ import annotations

import json
import math
import sys

from redflag import config
from redflag.analysis import run_analysis
from redflag.data_io import load_processed, to_jsonable
from redflag.report import render_all
from redflag.validation import assert_no_lookahead, build_panel


def _diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                yield f"{path}/{k}: missing on one side"
            else:
                yield from _diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}: list length {len(a)} != {len(b)}"
        else:
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                yield from _diff(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12):
            yield f"{path}: {a} != {b}"
    elif a != b:
        yield f"{path}: {a!r} != {b!r}"


def main() -> int:
    failures: list[str] = []
    fin, companies, cases = load_processed()
    panel = build_panel(fin, companies, cases)
    assert_no_lookahead(panel, cases)
    fresh = to_jsonable(run_analysis(panel, cases)["results"])
    on_disk = json.loads((config.REPORTS / "results.json").read_text())
    failures += [f"results.json stale: {d}" for d in _diff(fresh, on_disk)]

    try:
        rendered = render_all(config.ROOT)
    except ValueError as exc:
        failures.append(str(exc))
        rendered = {}
    for path, text in rendered.items():
        if not path.exists() or path.read_text() != text:
            failures.append(
                f"{path.relative_to(config.ROOT)} differs from a fresh render (run scripts/render_docs.py)"
            )

    if failures:
        print("CLAIM CHECK FAILED")
        print(*failures, sep="\n  ")
        return 1
    print(
        f"claim check passed: results.json reproduced; {len(rendered)} documents match their templates and results."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
