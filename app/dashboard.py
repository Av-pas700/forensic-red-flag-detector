"""Streamlit dashboard: watchlist, per-company score breakdown, trends and case studies.

Run with:  streamlit run app/dashboard.py
Reads only files produced by `make reproduce` (data/processed/scored_panel.csv, reports/results.json).
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from redflag import config
from redflag.benford import EXPECTED
from redflag.data_io import load_processed
from redflag.features import BENEISH_THRESHOLD

DISCLAIMER_TMPL = (
    "Screening tool, not investment advice. A flag indicates elevated risk that merits investigation; "
    "it is not proof of fraud or wrongdoing. The sample is {n} US companies with disclosed restatements plus "
    "matched peers; small-sample results are a case-study validation, not evidence of predictive power."
)
TESTS = {
    "mscore": ("Beneish M-score", "Weighted blend of eight indices"),
    "tata": ("Total accruals / assets", "Earnings not backed by operating cash flow"),
    "sloan_accruals": ("Sloan balance-sheet accruals", "Working-capital accruals / avg assets"),
    "ar_rev_gap": ("Receivables growth - revenue growth", "Sales booked but not collected"),
    "ni_cfo_gap_rev": ("(Net income - op. cash flow) / revenue", "Cash conversion gap"),
    "dsri": ("Days-sales-in-receivables index", "Receivables outpacing sales"),
    "aqi": ("Asset-quality index", "Rising share of soft assets"),
    "benford_mad": ("Benford MAD (first digits)", "Departure from expected leading-digit mix"),
}

st.set_page_config(page_title="Forensic Red-Flag Detector", page_icon="🔎", layout="wide")


@st.cache_data
def load_all():
    panel = pd.read_csv(config.DATA_PROCESSED / "scored_panel.csv", parse_dates=["filed", "fye"])
    _, _, cases = load_processed()
    results = json.loads((config.REPORTS / "results.json").read_text())
    return panel, cases, results


def percentile_vs_controls(panel: pd.DataFrame, col: str, value: float) -> float:
    ctrl = panel.loc[(panel["role"] == "control") & panel[col].notna(), col]
    return float((ctrl < value).mean() * 100) if len(ctrl) and pd.notna(value) else np.nan


def timeline(ax, d: pd.DataFrame, event=None, signal="gap"):
    d = d.sort_values("filed")
    if signal == "gap":
        y = d["score_core"] - d["thr_core"]
        ax.set_ylabel("Composite score - flag threshold")
    else:
        y = d["mscore"]
        ax.set_ylabel("Beneish M-score")
    base = 0.0 if signal == "gap" else BENEISH_THRESHOLD
    ax.axhline(base, color="k", lw=0.8)
    ax.plot(d["filed"], y, color="#9aa0a6", lw=1)
    mis = d["label"] == 1
    ax.scatter(d.loc[~mis, "filed"], y[~mis], color="#1b6ca8", s=28, zorder=3, label="10-K")
    ax.scatter(d.loc[mis, "filed"], y[mis], color="#d1495b", s=36, zorder=3, label="10-K with misstated year")
    if event is not None:
        ax.axvline(event, color="k", ls="--", lw=1)
        ax.text(event, ax.get_ylim()[1], " Item 4.02", va="top", fontsize=8)
    ax.legend(fontsize=7, loc="best")
    ax.grid(alpha=0.25)


panel, cases, results = load_all()
DISCLAIMER = DISCLAIMER_TMPL.format(n=results["sample"]["n_cases"])
st.title("Forensic Red-Flag Detector")
st.warning(DISCLAIMER)
m = results["metrics"]
c1, c2, c3, c4 = st.columns(4)


def _ci(k: str) -> str:
    d = m[k]
    return f"{d['estimate']:.2f} [{d['lo']:.2f}, {d['hi']:.2f}]"


c1.metric("Cases / matched controls", f"{results['sample']['n_cases']} / {results['sample']['n_controls']}")
c2.metric(
    "Beneish ROC-AUC [95% CI]", _ci("beneish_fixed.roc_auc"), help="Published M-score, leave-one-company-out"
)
c3.metric("Composite ROC-AUC [95% CI]", _ci("core.roc_auc"), help="Logistic regression on six signals")
c4.metric(
    "Cases flagged early (Beneish)",
    f"{results['lead']['beneish_fixed']['n_detected']} of {results['lead']['beneish_fixed']['n_cases']}",
    help="At least one misstated-year 10-K flagged before the restatement cut-off",
)

tab_watch, tab_company, tab_case, tab_about = st.tabs(
    ["Ranked watchlist", "Company view", "Case studies", "About"]
)

with tab_watch:
    st.caption(
        "Latest available 10-K per company. Case companies are shown only up to filings made **before** their "
        "restatement cut-off (no look-ahead). Scores are out-of-company (leave-one-company-out)."
    )
    latest = panel.sort_values("filed").groupby("cik").tail(1).copy()
    latest["composite_gap"] = latest["score_core"] - latest["thr_core"]
    role = st.radio("Show", ["All", "Case companies", "Control companies"], horizontal=True)
    if role != "All":
        latest = latest[latest["role"] == ("case" if role == "Case companies" else "control")]
    table = (
        latest.sort_values("composite_gap", ascending=False)[
            [
                "name",
                "role",
                "fyear",
                "filed",
                "composite_gap",
                "flag_core",
                "mscore",
                "flag_beneish_fixed",
                "tata",
                "ar_rev_gap",
            ]
        ]
        .assign(filed=lambda d: d["filed"].dt.date)
        .rename(
            columns={
                "name": "Company",
                "role": "Role",
                "fyear": "Fiscal year",
                "filed": "10-K filed",
                "composite_gap": "Composite score - threshold",
                "flag_core": "Composite flag",
                "mscore": "Beneish M",
                "flag_beneish_fixed": "Beneish flag (>-1.78)",
                "tata": "TATA",
                "ar_rev_gap": "AR - revenue growth",
            }
        )
    )
    st.dataframe(table, hide_index=True, use_container_width=True)

with tab_company:
    names = panel.drop_duplicates("cik").sort_values("name")
    pick = st.selectbox("Company", names["name"].tolist())
    cik = int(names.loc[names["name"] == pick, "cik"].iloc[0])
    d = panel[panel["cik"] == cik].sort_values("filed")
    years = d["fyear"].tolist()
    fy = st.select_slider("Fiscal year", options=years, value=years[-1])
    row = d[d["fyear"] == fy].iloc[0]
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Score breakdown by test")
        rows = []
        for col, (label, why) in TESTS.items():
            pct = percentile_vs_controls(panel, col, row[col])
            rows.append(
                {"Test": label, "Value": row[col], "Percentile vs control 10-Ks": pct, "Meaning": why}
            )
        bd = pd.DataFrame(rows)
        fig, ax = plt.subplots(figsize=(5.5, 3.4))
        ax.barh(bd["Test"], bd["Percentile vs control 10-Ks"].fillna(0), color="#1b6ca8")
        ax.axvline(90, color="#d1495b", ls="--", lw=1)
        ax.set_xlim(0, 100)
        ax.set_xlabel("Percentile among control-company 10-Ks (dashed = 90th)")
        ax.invert_yaxis()
        st.pyplot(fig)
        plt.close(fig)
        st.dataframe(bd, hide_index=True, use_container_width=True)
        flagged = bool(row["flag_core"]) if pd.notna(row["flag_core"]) else False
        st.markdown(
            f"**Composite:** {'FLAG (elevated risk)' if flagged else 'no flag'}  |  "
            f"**Beneish M:** {row['mscore']:.2f} ({'above' if row['mscore'] > BENEISH_THRESHOLD else 'below'} {BENEISH_THRESHOLD})"
        )
    with right:
        st.subheader("Historical trend")
        fig, ax = plt.subplots(figsize=(5.5, 2.6))
        timeline(ax, d, signal="m")
        st.pyplot(fig)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(5.5, 2.6))
        timeline(ax, d, signal="gap")
        st.pyplot(fig)
        plt.close(fig)
        st.subheader("Benford first-digit profile")
        counts = row[[f"bd{i}" for i in range(1, 10)]].to_numpy(dtype=float)
        fig, ax = plt.subplots(figsize=(5.5, 2.4))
        ax.bar(range(1, 10), counts / counts.sum(), color="#9aa0a6", label="Reported values")
        ax.plot(range(1, 10), EXPECTED, color="k", marker="o", label="Benford")
        ax.legend(fontsize=7)
        st.pyplot(fig)
        plt.close(fig)
        st.caption(
            f"n = {int(row['benford_n'])} values, MAD = {row['benford_mad']:.4f}. "
            + (
                "Sample is below the ~110 needed for a reliable chi-square."
                if int(row["benford_n"]) < 110
                else ""
            )
        )

with tab_case:
    cases_sorted = cases.sort_values("company")
    cname = st.selectbox("Case", cases_sorted["company"].tolist())
    c = cases_sorted[cases_sorted["company"] == cname].iloc[0]
    d = panel[panel["cik"] == int(c["cik"])].sort_values("filed")
    a, b = st.columns([2, 1])
    with a:
        fig, ax = plt.subplots(figsize=(7, 3.2))
        timeline(ax, d, event=c["nonreliance_date"], signal="gap")
        ax.set_title(f"{cname}: composite score vs threshold (only filings before the cut-off)")
        st.pyplot(fig)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 3.0))
        timeline(ax, d, event=c["nonreliance_date"], signal="m")
        st.pyplot(fig)
        plt.close(fig)
    with b:
        mis = d[d["label"] == 1]
        hit = mis[mis["flag_core"]]
        st.markdown(f"**Non-reliance 8-K (Item 4.02):** {c['nonreliance_date']:%d %b %Y}  ")
        st.markdown(f"[Primary source on EDGAR]({c['nonreliance_url']})")
        st.markdown(f"**What was restated:** {c['restated_what']}")
        if pd.notna(c["first_signal_date"]):
            st.markdown(
                f"**Earlier verified public signal:** {c['first_signal_date']:%d %b %Y} ([filing]({c['first_signal_url']}))"
            )
        st.markdown(
            f"**SEC action:** {c['enforcement_date']:%d %b %Y} - [{c['enforcement_note']}]({c['enforcement_url']})"
        )
        if pd.notna(c["bankruptcy_date"]):
            st.markdown(
                f"**Chapter 11 8-K (Item 1.03):** {c['bankruptcy_date']:%d %b %Y} ([filing]({c['bankruptcy_url']}))"
            )
        st.markdown("---")
        if len(hit):
            first = hit["filed"].min()
            days = (c["cutoff"] - first).days
            st.success(
                f"Composite flagged the FY{int(hit.loc[hit['filed'].idxmin(), 'fyear'])} 10-K filed {first:%d %b %Y}: "
                f"{days / 365.25:.1f} years ({days / 91.3125:.0f} quarters) before the cut-off."
            )
        else:
            st.error("Composite did NOT flag any misstated-year 10-K filed before the cut-off.")
        bh = mis[mis["flag_beneish_fixed"]]
        st.write(f"Beneish at -1.78 flagged {len(bh)} of {len(mis)} misstated-year 10-Ks.")

with tab_about:
    st.markdown(
        f"""
**What this is.** Four families of published screening tests (Beneish M-score, accrual quality, receivables/cash-flow
divergence, Benford first-digit) computed from SEC XBRL filings, combined in a small class-weighted logistic regression
and validated against {results["sample"]["n_cases"]} real US restatement cases with leave-one-company-out cross-validation.

**Look-ahead discipline.** Each fiscal year is built only from the facts in that year's original 10-K, and a case
company's filings are cut off at the earlier of its Item 4.02 date and the first verified public signal.

**Holdout test.** {results["development"]["sample"]["n_cases"]} development cases were chosen from memory; {results["holdout"]["n_cases"]} holdout cases were selected mechanically from SEC enforcement releases
under rules committed to GitHub before scoring (docs/preregistration.md). The Beneish M-score scores a ROC-AUC of
{results["development"]["metrics"]["beneish_fixed.roc_auc"]["estimate"]:.2f} on the development cases and
{results["holdout"]["metrics"]["beneish_fixed.roc_auc"]["estimate"]:.2f}
[{results["holdout"]["metrics"]["beneish_fixed.roc_auc"]["lo"]:.2f}, {results["holdout"]["metrics"]["beneish_fixed.roc_auc"]["hi"]:.2f}] on the holdout:
it did not generalise.

**Honest limits.** {results["sample"]["n_positive_rows"]} misstated firm-years across {results["sample"]["n_cases"]}
companies; selection of cases is made in hindsight; controls are screened only for Item 4.02 filings; the sample base rate
is far higher than the real-world rate, so precision figures overstate live performance.

{DISCLAIMER}
"""
    )
