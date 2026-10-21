"""Download SEC data, verify the case set, match controls and write data/processed/*.

Requires SEC_USER_AGENT. Raw JSON is cached in data/raw, so reruns are cheap and polite.
Usage: python scripts/build_dataset.py
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from redflag import config
from redflag.cases import load_cases, verify_cases
from redflag.controls import missing_inputs, select_controls, usable_years
from redflag.edgar import EdgarClient
from redflag.statements import extract_annual_statements


def main() -> None:
    client = EdgarClient()
    cases = verify_cases(client, load_cases())
    log: list[str] = []

    stm_by_cik: dict[int, pd.DataFrame] = {}
    kept = []
    for _, c in cases.iterrows():
        cik = int(c["cik"])
        stm = extract_annual_statements(client.company_facts(cik), cik)
        pre = stm[stm["filed"] < c["cutoff"]]
        if not usable_years(pre, list(c["positive_fyears"])):
            log.append(
                f"DROPPED case {c['case_id']}: pre-cutoff 10-K data incomplete for "
                f"{c['positive_fyears']} (missing {missing_inputs(pre, c['positive_fyears'])})"
            )
            print(log[-1])
            continue
        stm_by_cik[cik] = stm
        kept.append(c)
    cases = pd.DataFrame(kept).reset_index(drop=True)

    case_ciks = {int(x) for x in cases["cik"]}
    controls: list[dict] = []
    used = set(case_ciks)
    for _, c in cases.iterrows():
        chosen = select_controls(client, c, stm_by_cik[int(c["cik"])], used, per_case=3)
        print(f"{c['case_id']}: {len(chosen)} controls -> {[x['name'] for x in chosen]}")
        if len(chosen) < 3:
            log.append(f"case {c['case_id']}: only {len(chosen)} controls found")
        for x in chosen:
            used.add(x["cik"])
            stm_by_cik[x["cik"]] = extract_annual_statements(client.company_facts(x["cik"]), x["cik"])
        controls.extend(chosen)
    controls_df = pd.DataFrame(controls)

    # company table + stacked statements
    rows = []
    for _, c in cases.iterrows():
        sub = client.submissions(int(c["cik"]))
        rows.append(
            {
                "cik": int(c["cik"]),
                "name": c["company"],
                "sic": sub.get("sic"),
                "sic_desc": sub.get("sicDescription"),
                "role": "case",
                "case_id": c["case_id"],
            }
        )
    for _, x in controls_df.iterrows():
        sub = client.submissions(int(x["cik"]))
        rows.append(
            {
                "cik": int(x["cik"]),
                "name": sub.get("name", x["name"]),
                "sic": sub.get("sic"),
                "sic_desc": sub.get("sicDescription"),
                "role": "control",
                "case_id": x["case_id"],
            }
        )
    companies = pd.DataFrame(rows)
    fin = pd.concat([stm_by_cik[int(k)].assign(cik=int(k)) for k in companies["cik"]], ignore_index=True)

    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    fin.to_csv(config.DATA_PROCESSED / "financials.csv", index=False)
    companies.to_csv(config.DATA_PROCESSED / "companies.csv", index=False)
    cases.assign(positive_fyears=cases["positive_fyears"].apply(lambda xs: ";".join(map(str, xs)))).to_csv(
        config.DATA_PROCESSED / "cases_verified.csv", index=False
    )
    controls_df.to_csv(config.DATA_PROCESSED / "controls.csv", index=False)
    (config.DATA_PROCESSED / "build_log.json").write_text(json.dumps(log, indent=2))
    print(f"cases kept: {len(cases)}, controls: {len(controls_df)}, 10-K rows: {len(fin)}")
    if log:
        print("LOG:", *log, sep="\n  ")
    sys.exit(0)


if __name__ == "__main__":
    main()
