"""Append mechanically selected holdout cases (data/cases/holdout_selected.csv) to data/cases/cases.csv.

Idempotent. The 14 original cases keep ``cohort = development``; appended rows get ``cohort = holdout``.
"""

from __future__ import annotations

import re

import pandas as pd

from redflag import config
from redflag.discovery import company_name


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())[:18]


def main() -> None:
    path = config.DATA_CASES / "cases.csv"
    cases = pd.read_csv(path, dtype={"first_signal_accn": str, "first_signal_date": str})
    if "cohort" not in cases:
        cases["cohort"] = "development"
    cases = cases[cases["cohort"] == "development"]  # rebuild the holdout block from scratch each time
    sel = pd.read_csv(config.DATA_CASES / "holdout_selected.csv")
    rows = []
    for _, r in sel.iterrows():
        if int(r["cik"]) in set(cases["cik"]):
            continue
        name = company_name(r["aaer_title"]) or str(r["edgar_name"]).title()
        fys = r["positive_fyears"].replace(".0", "")
        rows.append(
            {
                "case_id": slug(name),
                "company": name,
                "cik": int(r["cik"]),
                "sic_note": f"SIC {int(r['sic'])}",
                "nonreliance_accn": r["accn_402"],
                "nonreliance_date": r["date_402"],
                "positive_fyears": fys,
                "restated_what": f"FY{fys.replace(';', ', ')} named in both the Item 4.02 8-K and the SEC order",
                "first_signal_accn": "",
                "first_signal_date": "",
                "first_signal_note": "",
                "enforcement_date": r["aaer_date"],
                "enforcement_url": r["aaer_url"],
                "enforcement_note": f"AAER-{int(r['aaer_no'])}: {r['aaer_title']}",
                "cohort": "holdout",
            }
        )
    out = pd.concat([cases, pd.DataFrame(rows)], ignore_index=True)
    types = pd.read_csv(config.DATA_CASES / "issue_types.csv")[["case_id", "issue_type"]]
    out = out.drop(columns=["issue_type"], errors="ignore").merge(types, on="case_id", how="left")
    out.to_csv(path, index=False)
    print(f"{len(rows)} holdout cases appended; total {len(out)} ({out['cohort'].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
