"""Render README.md, reports/memo.md, CV_BULLETS.md and docs/case_selection.md from templates + results.json."""

from __future__ import annotations

from redflag import config
from redflag.report import render_all


def main() -> None:
    for path, text in render_all(config.ROOT).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
