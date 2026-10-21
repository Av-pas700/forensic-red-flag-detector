"""Run the full analysis from data/processed and write results, tables and figures.

No network access is needed. Usage: python scripts/run_analysis.py
"""

from __future__ import annotations

import pandas as pd

from redflag import config, plotting
from redflag.analysis import run_analysis
from redflag.data_io import load_processed, write_json
from redflag.validation import assert_no_lookahead, build_panel


def main() -> None:
    fin, companies, cases = load_processed()
    panel = build_panel(fin, companies, cases)
    assert_no_lookahead(panel, cases)

    out = run_analysis(panel, cases)
    results, tables, scored, ev_index = out["results"], out["tables"], out["scored"], out["eval_index"]
    ev = panel.loc[ev_index]

    write_json(config.REPORTS / "results.json", results)
    tdir = config.REPORTS / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(tdir / f"{name}.csv", index=False)

    # scored panel for the dashboard: every scorable 10-K with out-of-company scores
    sp = panel.copy()
    for k, sc in scored.items():
        sp[f"score_{k}"] = sc["score"]
        sp[f"flag_{k}"] = sc["score"] > sc["threshold"]
        sp[f"thr_{k}"] = sc["threshold"]
    sp.to_csv(config.DATA_PROCESSED / "scored_panel.csv", index=False)

    fdir = config.FIGURES
    plotting.plot_roc_pr(ev, scored, results, fdir / "fig1_roc_pr.png")
    plotting.plot_case_timelines(panel, scored["core"], cases, fdir / "fig2_case_timelines.png")
    outcomes = {k: tables[f"case_outcomes_{k}"] for k in ("core", "beneish")}
    plotting.plot_lead_times(
        {"core": outcomes["core"], "beneish_fixed": outcomes["beneish"]}, fdir / "fig3_lead_times.png"
    )
    plotting.plot_mscore(ev, results["beneish_threshold"], fdir / "fig4_mscore_distribution.png")
    plotting.plot_benford(ev, fdir / "fig5_benford.png")
    plotting.plot_single_signals(results, fdir / "fig6_single_signals.png")
    print(pd.Series(results["sample"]).to_string())


if __name__ == "__main__":
    main()
