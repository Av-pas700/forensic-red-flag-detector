"""Share of all US calendar-year filers that the M-score flags (base-rate check). Needs SEC_USER_AGENT.

Writes data/processed/universe.json, which run_analysis.py folds into results.json.
Usage: python scripts/universe_check.py
"""

from __future__ import annotations

from redflag import config
from redflag.data_io import write_json
from redflag.edgar import EdgarClient
from redflag.universe import build_universe, flag_rate

YEARS = (2015, 2019)


def main() -> None:
    client = EdgarClient()
    out = {}
    for y in YEARS:
        out[str(y)] = flag_rate(build_universe(client, y))
        print(y, out[str(y)])
    write_json(config.DATA_PROCESSED / "universe.json", out)


if __name__ == "__main__":
    main()
