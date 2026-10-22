"""Render README / memo / CV bullets from templates using only numbers in ``results.json``.

Templates contain ``{{key}}`` placeholders. :func:`build_values` is the *only* place numbers are
formatted, so every figure quoted in a document traces to code that ran. ``scripts/check_claims.py``
re-renders and compares with the files on disk, and refuses templates that contain hand-typed decimals.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
DECIMAL = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")


def f2(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"


def pct(x, digits: int = 0) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{digits}f}%"


def with_ci(m: dict) -> str:
    """Compact form for tables: 0.70 [0.59, 0.80]."""
    return f"{f2(m['estimate'])} [{f2(m['lo'])}, {f2(m['hi'])}]"


def ci_prose(m: dict) -> str:
    return f"{f2(m['estimate'])} (95% CI {f2(m['lo'])} to {f2(m['hi'])})"


def _verdict_vs_baseline(diff: dict, name: str) -> str:
    est, lo, hi = diff["estimate"], diff["lo"], diff["hi"]
    if lo > 0:
        return f"{name} ranked misstated years better than the baseline (ROC-AUC difference {f2(est)}, 95% CI {f2(lo)} to {f2(hi)})."
    if hi < 0:
        return f"{name} ranked misstated years WORSE than the published baseline (ROC-AUC difference {f2(est)}, 95% CI {f2(lo)} to {f2(hi)})."
    return f"{name} was statistically indistinguishable from the published baseline (ROC-AUC difference {f2(est)}, 95% CI {f2(lo)} to {f2(hi)})."


def build_values(results: dict, outcomes: dict[str, pd.DataFrame], cases: pd.DataFrame) -> dict[str, str]:
    m, s, lead = results["metrics"], results["sample"], results["lead"]
    v: dict[str, str] = {}
    v["n_cases"] = str(s["n_cases"])
    v["n_controls"] = str(s["n_controls"])
    v["n_pos"] = str(s["n_positive_rows"])
    v["n_neg"] = str(s["n_negative_rows"])
    v["n_rows"] = str(s["n_rows_total"])
    v["pos_share"] = pct(s["positive_share"])
    v["fy_min"], v["fy_max"] = str(s["fyear_min"]), str(s["fyear_max"])
    v["n_boot"] = str(results["n_boot"])
    v["beneish_threshold"] = f"{results['beneish_threshold']}"

    for k in ("beneish_fixed", "core", "extended", "anchored"):
        v[f"auc_{k}"] = with_ci(m[f"{k}.roc_auc"])
        v[f"auc_{k}_full"] = ci_prose(m[f"{k}.roc_auc"])
        v[f"auc_{k}_pt"] = f2(m[f"{k}.roc_auc"]["estimate"])
        v[f"pr_{k}"] = with_ci(m[f"{k}.pr_auc"])
        v[f"prec_{k}"] = pct(m[f"{k}.precision"]["estimate"])
        v[f"rec_{k}"] = pct(m[f"{k}.recall"]["estimate"])
        v[f"fpr_{k}"] = pct(m[f"{k}.fpr"]["estimate"])
        v[f"rec_{k}_ci"] = f"{pct(m[f'{k}.recall']['lo'])} to {pct(m[f'{k}.recall']['hi'])}"
        v[f"fpr_{k}_ci"] = f"{pct(m[f'{k}.fpr']['lo'])} to {pct(m[f'{k}.fpr']['hi'])}"
        v[f"prec_{k}_ci"] = f"{pct(m[f'{k}.precision']['lo'])} to {pct(m[f'{k}.precision']['hi'])}"
    for k in ("core", "extended", "anchored"):
        d = m[f"diff_auc.{k}_minus_beneish"]
        v[f"diff_{k}_pt"] = f2(d["estimate"])
        v[f"diff_{k}_lo"], v[f"diff_{k}_hi"] = f2(d["lo"]), f2(d["hi"])
        v[f"diff_{k}"] = f"{f2(d['estimate'])} (95% CI {f2(d['lo'])} to {f2(d['hi'])})"
        v[f"verdict_{k}"] = _verdict_vs_baseline(
            d,
            {
                "core": "The pre-specified composite",
                "extended": "The extended composite",
                "anchored": "The post-hoc anchored composite",
            }[k],
        )
    v["pr_prevalence"] = pct(s["positive_share"])
    perm = results["permutation_p"]
    for k in ("beneish_fixed", "core", "extended", "anchored"):
        v[f"perm_{k}"] = "<0.001" if perm[k] < 0.001 else f"{perm[k]:.3f}"

    for k in ("beneish_fixed", "core", "extended", "anchored", "beneish_p90"):
        L = lead[k]
        v[f"det_{k}"] = f"{L['n_detected']} of {L['n_cases']}"
        v[f"det_{k}_n"] = str(L["n_detected"])
        v[f"anyflag_{k}"] = f"{L['n_flagged_any_pre_event']} of {L['n_cases']}"
        v[f"lead_med_y_{k}"] = f2(L["median_lead_years"])
        v[f"lead_med_q_{k}"] = (
            f"{L['median_lead_quarters']:.0f}" if L["median_lead_quarters"] is not None else "n/a"
        )
        v[f"lead_min_y_{k}"] = f2(L["min_lead_years"])
        v[f"lead_max_y_{k}"] = f2(L["max_lead_years"])
    v["n_cases_total"] = str(lead["core"]["n_cases"])

    for k in ("beneish_fixed", "core", "anchored"):
        for p, val in results["ppv_at_prevalence"][k].items():
            v[f"ppv_{k}_{int(round(float(p) * 100))}"] = pct(val, 1)
        v[f"jack_{k}"] = (
            f"{f2(results['jackknife_auc'][k]['min'])} to {f2(results['jackknife_auc'][k]['max'])}"
        )

    for sig, d in results["single_signals"].items():
        v[f"sig_{sig}"] = with_ci(d)
        v[f"sig_{sig}_full"] = ci_prose(d)
        v[f"sig_{sig}_pt"] = f2(d["estimate"])
    b = results["benford"]
    v["bf_med_cases"] = f"{b['median_mad_cases']:.4f}"
    v["bf_med_controls"] = f"{b['median_mad_controls']:.4f}"
    v["bf_nonconf_cases"] = pct(b["share_nonconforming_cases"])
    v["bf_nonconf_controls"] = pct(b["share_nonconforming_controls"])
    v["bf_med_n"] = f"{b['median_n_values']:.0f}"
    v["bf_share_reliable"] = pct(b["share_reliable_n"])

    for k in ("beneish_fixed", "core", "extended", "anchored"):
        a = m[f"{k}.roc_auc"]
        v[f"auc_{k}_lo"], v[f"auc_{k}_hi"] = f2(a["lo"]), f2(a["hi"])
    others = {k: d for k, d in results["single_signals"].items() if k != "mscore" and not k.endswith("_ops")}
    best = max(others, key=lambda k: others[k]["estimate"])
    v["best_other_name"], v["best_other_pt"] = best, ci_prose(others[best])
    v["n_bankrupt"] = str(int(cases["bankruptcy_date"].notna().sum()))
    v["n_tests"] = str(count_tests())
    sig_ps = [perm[k] for k in ("beneish_fixed", "core")]
    if all(p < 0.05 for p in sig_ps):
        v["perm_reading"] = (
            "Both rank misstated years better than chance would, although the confidence intervals are wide."
        )
    elif sig_ps[0] < 0.05:
        v["perm_reading"] = "Only the baseline ranks misstated years better than chance would."
    else:
        v["perm_reading"] = "Neither is clearly better than chance at this sample size."

    def lead_dev(k):
        L = results["development"]["lead"][k]
        return f"{L['n_detected']} of {L['n_cases']}"

    # holdout / development / universe / sensitivity --------------------------------------
    h, d = results["holdout"], results["development"]
    hm, dm = h["metrics"], d["metrics"]
    v["h_n_cases"], v["h_n_controls"] = str(h["n_cases"]), str(h["n_controls"])
    v["h_n_pos"], v["h_n_neg"] = str(h["n_positive_rows"]), str(h["n_negative_rows"])
    v["d_n_cases"], v["d_n_controls"] = str(d["sample"]["n_cases"]), str(d["sample"]["n_controls"])
    for k in ("beneish_fixed", "core"):
        v[f"h_auc_{k}"] = with_ci(hm[f"{k}.roc_auc"])
        v[f"h_auc_{k}_full"] = ci_prose(hm[f"{k}.roc_auc"])
        v[f"h_auc_{k}_pt"] = f2(hm[f"{k}.roc_auc"]["estimate"])
        v[f"h_auc_{k}_lo"], v[f"h_auc_{k}_hi"] = f2(hm[f"{k}.roc_auc"]["lo"]), f2(hm[f"{k}.roc_auc"]["hi"])
        v[f"h_pr_{k}"] = with_ci(hm[f"{k}.pr_auc"])
        v[f"h_rec_{k}"] = pct(hm[f"{k}.recall"]["estimate"])
        v[f"h_fpr_{k}"] = pct(hm[f"{k}.fpr"]["estimate"])
        v[f"h_det_{k}"] = f"{h['lead'][k]['n_detected']} of {h['lead'][k]['n_cases']}"
        v[f"h_lead_med_y_{k}"] = f2(h["lead"][k]["median_lead_years"])
        v[f"d_auc_{k}"] = with_ci(dm[f"{k}.roc_auc"])
        v[f"d_auc_{k}_full"] = ci_prose(dm[f"{k}.roc_auc"])
        v[f"d_auc_{k}_pt"] = f2(dm[f"{k}.roc_auc"]["estimate"])
        v[f"h_perm_{k}"] = "<0.001" if h["permutation_p"][k] < 0.001 else f"{h['permutation_p'][k]:.3f}"
    v["h_diff_core"] = ci_prose(hm["diff_auc.core_minus_beneish"])
    b = hm["beneish_fixed.roc_auc"]
    if b["lo"] > 0.5:
        v["h_reading"] = (
            "The M-score ranked misstated years above control years on cases it had never seen, with the lower end of the interval above chance."
        )
    elif b["estimate"] > 0.5:
        v["h_reading"] = (
            "The M-score's point estimate on unseen cases is above chance, but the interval includes chance, so the holdout does not confirm the development result."
        )
    else:
        v["h_reading"] = (
            "The M-score did no better than chance on unseen cases, so the development result did not generalise."
        )
    c = hm["core.roc_auc"]
    v["h_core_reading"] = (
        "The frozen composite also ranked above chance."
        if c["lo"] > 0.5
        else "The frozen composite's interval includes chance."
    )

    uni = results.get("universe", {})
    years = sorted(uni)
    for y in years:
        v[f"u_flag_{y}"] = pct(uni[y]["flag_share"])
        v[f"u_n_{y}"] = f"{uni[y]['n_scored']:,}"
        v[f"ppv_univ_1_{y}"] = pct(m["beneish_fixed.recall"]["estimate"] * 0.01 / uni[y]["flag_share"], 1)
    if years:
        shares = [uni[y]["flag_share"] for y in years]
        v["u_range"] = f"{pct(min(shares))} to {pct(max(shares))}"
        v["u_range_dash"] = f"{pct(min(shares))}-{pct(max(shares))}"
        ppvs = [m["beneish_fixed.recall"]["estimate"] * 0.01 / uni[y]["flag_share"] for y in years]
        v["ppv_univ_range"] = f"{pct(min(ppvs), 1)}-{pct(max(ppvs), 1)}"
        v["u_years"] = " and ".join(years)

    bt = results.get("by_issue_type", {})
    if "revenue" in bt and "other" in bt:
        r_, o_ = bt["revenue"]["beneish_fixed.roc_auc"], bt["other"]["beneish_fixed.roc_auc"]
        v["bt_rev_cases"], v["bt_oth_cases"] = str(bt["revenue"]["n_cases"]), str(bt["other"]["n_cases"])
        v["bt_rev_pos"], v["bt_oth_pos"] = (
            str(bt["revenue"]["n_positive_rows"]),
            str(bt["other"]["n_positive_rows"]),
        )
        v["bt_rev_auc"], v["bt_oth_auc"] = ci_prose(r_), ci_prose(o_)
        v["bt_rev_rec"] = pct(bt["revenue"]["beneish_fixed.recall"]["estimate"])
        v["bt_oth_rec"] = pct(bt["other"]["beneish_fixed.recall"]["estimate"])
        if r_["lo"] > 0.5 and o_["lo"] <= 0.5:
            v["bt_reading"] = (
                "The M-score separates revenue-type cases from controls but not the others - consistent with it being built for "
                "revenue and receivable manipulation. The two intervals overlap, the grouping was made after I saw the holdout result, and the cell sizes are small, "
                "so this is a hypothesis for a pre-registered follow-up, not a finding."
            )
        else:
            v["bt_reading"] = "The split by restatement type does not clearly explain the holdout result."

    so = results["sensitivity_ops"]
    v["ops_auc_full"] = ci_prose(so["auc_ops"])
    v["ops_diff_full"] = ci_prose(so["diff"])
    v["ops_reading"] = (
        "Using continuing-operations income did not change the conclusion."
        if so["diff"]["lo"] <= 0 <= so["diff"]["hi"]
        else "Using continuing-operations income changed the ranking measurably."
    )

    # tables --------------------------------------------------------------------------------
    rows = [
        "| Model | ROC-AUC [95% CI] | PR-AUC [95% CI] | Recall (misstated 10-Ks) | False-positive rate (control 10-Ks) | Cases flagged pre-event |",
        "|---|---|---|---|---|---|",
    ]
    names = {
        "beneish_fixed": "Beneish M-score > -1.78 (baseline)",
        "core": "Composite, 6 signals (pre-specified)",
        "extended": "Composite + Benford + NI-CFO gap",
        "anchored": "M-score + 3 signals (post hoc, exploratory)",
    }
    for k, label in names.items():
        rows.append(
            f"| {label} | {v[f'auc_{k}']} | {v[f'pr_{k}']} | {v[f'rec_{k}']} | {v[f'fpr_{k}']} | {v[f'det_{k}']} |"
        )
    v["table_models"] = "\n".join(rows)

    sig_rows = ["| Signal (raw, higher = riskier) | ROC-AUC [95% CI] |", "|---|---|"]
    for sig, d in sorted(results["single_signals"].items(), key=lambda kv: -kv[1]["estimate"]):
        sig_rows.append(f"| {sig} | {with_ci(d)} |")
    v["table_signals"] = "\n".join(sig_rows)

    core = outcomes["core"].set_index("case_id")
    base = outcomes["beneish_fixed"].set_index("case_id")
    rows = [
        "| Case | Misstated 10-Ks scored | Item 4.02 filed | Beneish flag: lead (yrs) | Composite flag: lead (yrs) |",
        "|---|---|---|---|---|",
    ]
    for _, c in cases.sort_values("nonreliance_date").iterrows():
        cid = c["case_id"]

        rows.append(
            f"| {c['company']} | {int(core.loc[cid, 'n_misstated_10k'])} | {c['nonreliance_date']:%Y-%m-%d} | {_lead_cell(base, cid)} | {_lead_cell(core, cid)} |"
        )
    v["table_cases"] = "\n".join(rows)
    # generalisation table (development vs untouched holdout vs pooled)
    g = [
        "| Model | Development cases (LOCO) | Holdout cases (frozen rules) | Pooled (LOCO) |",
        "|---|---|---|---|",
    ]
    for k, label in (("beneish_fixed", "Beneish M-score > -1.78"), ("core", "Composite, 6 signals")):
        g.append(f"| {label}: ROC-AUC [95% CI] | {v[f'd_auc_{k}']} | {v[f'h_auc_{k}']} | {v[f'auc_{k}']} |")
    for k, label in (("beneish_fixed", "Beneish M-score > -1.78"), ("core", "Composite, 6 signals")):
        g.append(
            f"| {label}: recall / false-positive rate | {pct(dm[f'{k}.recall']['estimate'])} / {pct(dm[f'{k}.fpr']['estimate'])} "
            f"| {v[f'h_rec_{k}']} / {v[f'h_fpr_{k}']} | {v[f'rec_{k}']} / {v[f'fpr_{k}']} |"
        )
        g.append(
            f"| {label}: cases flagged before cut-off | {lead_dev(k)} | {v[f'h_det_{k}']} | {v[f'det_{k}']} |"
        )
    v["table_generalisation"] = "\n".join(g)

    hc = outcomes.get("holdout_core")
    hb = outcomes.get("holdout_beneish_fixed")
    if hc is not None and hb is not None:
        hc, hb = hc.set_index("case_id"), hb.set_index("case_id")
        hrows = [
            "| Holdout case | Misstated 10-Ks scored | Item 4.02 filed | Beneish flag: lead (yrs) | Composite flag: lead (yrs) |",
            "|---|---|---|---|---|",
        ]
        for _, c in cases[cases["cohort"] == "holdout"].sort_values("nonreliance_date").iterrows():
            cid = c["case_id"]
            hrows.append(
                f"| {c['company']} | {int(hc.loc[cid, 'n_misstated_10k'])} | {c['nonreliance_date']:%Y-%m-%d} | {_lead_cell(hb, cid)} | {_lead_cell(hc, cid)} |"
            )
        v["table_holdout_cases"] = "\n".join(hrows)

    return v


def _lead_cell(df: pd.DataFrame, cid: str) -> str:
    r = df.loc[cid]
    return f"{r['lead_years']:.1f}" if r["detected"] else "not flagged"


def render(template: str, values: dict[str, str]) -> str:
    missing = sorted({k for k in PLACEHOLDER.findall(template) if k not in values})
    if missing:
        raise KeyError(f"template uses unknown placeholders: {missing}")
    return PLACEHOLDER.sub(lambda mo: values[mo.group(1)], template)


def stray_decimals(template: str) -> list[str]:
    """Hand-typed decimals in a template (outside code fences and placeholders)."""
    text = re.sub(r"```.*?```", "", template, flags=re.S)
    text = PLACEHOLDER.sub("", text)
    # Python versions and SEC Form 8-K item numbers are identifiers, not results.
    allowed = {"3.10", "3.11", "3.12", "4.02", "1.03"}
    return [d for d in DECIMAL.findall(text) if d not in allowed]


def _md_link(text: str, url: str) -> str:
    return f"[{text}]({url})" if isinstance(url, str) and url else text


def case_doc_values(
    cases: pd.DataFrame,
    controls: pd.DataFrame,
    companies: pd.DataFrame,
    excluded: pd.DataFrame,
    build_log: list[str],
) -> dict[str, str]:
    """Tables for docs/case_selection.md (every row comes from verified CSVs)."""
    rows = [
        "| Case | Cohort | CIK | Item 4.02 8-K (primary source) | Earlier verified signal | Fiscal years labelled misstated | What was misstated | SEC action | Chapter 11 (Item 1.03) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, c in cases.sort_values("nonreliance_date").iterrows():
        sig = (
            (
                _md_link(f"{c['first_signal_date']:%Y-%m-%d}", c["first_signal_url"])
                + f" ({c['first_signal_note']})"
            )
            if pd.notna(c["first_signal_date"])
            else "none verified"
        )
        bk = (
            _md_link(f"{c['bankruptcy_date']:%Y-%m-%d}", c["bankruptcy_url"])
            if pd.notna(c["bankruptcy_date"])
            else "none"
        )
        fys = ", ".join(str(y) for y in c["positive_fyears"])
        nr = _md_link(c["nonreliance_date"].strftime("%Y-%m-%d"), c["nonreliance_url"])
        enf = _md_link(c["enforcement_date"].strftime("%Y-%m-%d"), c["enforcement_url"])
        rows.append(
            f"| {c['company']} | {c.get('cohort', 'development')} | {c['cik']} | {nr} | {sig} | {fys} | {c['restated_what']} | "
            f"{enf}: {c['enforcement_note']} | {bk} |"
        )
    out = {"table_case_sources": "\n".join(rows)}

    names = companies.set_index("cik")["name"]
    crow = ["| Case | Control | CIK | SIC | Match level | log size gap |", "|---|---|---|---|---|---|"]
    for _, x in controls.sort_values(["case_id", "log_size_gap"]).iterrows():
        crow.append(
            f"| {x['case_id']} | {names.get(x['cik'], x['name'])} | {x['cik']} | {x['sic']} | {x['match_level']} | {x['log_size_gap']:.2f} |"
        )
    out["table_controls"] = "\n".join(crow)
    out["n_controls_tbl"] = str(len(controls))
    tiers = controls["match_level"].value_counts()
    out["match_tiers"] = ", ".join(f"{n} at {t}" for t, n in tiers.items())

    erow = ["| Candidate | Why it is not in the analysis | Evidence |", "|---|---|---|"]
    for _, e in excluded.iterrows():
        erow.append(f"| {e['company']} | {e['reason']} | {e['evidence']} |")
    out["table_excluded"] = "\n".join(erow)
    rej_path = Path(__file__).resolve().parents[2] / "data" / "cases" / "holdout_rejected.csv"
    if rej_path.is_file():
        rej = pd.read_csv(rej_path)
        rrows = ["| AAER company | AAER date | Why it is not in the holdout |", "|---|---|---|"]
        rrows += [f"| {r['company']} | {r['aaer_date']} | {r['reason']} |" for _, r in rej.iterrows()]
        out["table_holdout_rejected"] = "\n".join(rrows)
        out["n_holdout_rejected"] = str(len(rej))
    out["build_log"] = "\n".join(f"- {line}" for line in build_log) if build_log else "- (none)"
    out["n_cases_tbl"] = str(len(cases))
    return out


def count_tests(root: Path | None = None) -> int:
    """Number of ``test_*`` functions under tests/ (parsed, not run)."""
    import ast

    root = root or Path(__file__).resolve().parents[2] / "tests"
    total = 0
    for f in root.glob("test_*.py"):
        total += sum(
            isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
            for n in ast.walk(ast.parse(f.read_text()))
        )
    return total


def narrative_guards(results: dict) -> list[str]:
    """Assumptions baked into the hand-written narrative; a failure means the prose needs re-reading."""
    m, sig = results["metrics"], results["single_signals"]
    bad = []
    base = m["beneish_fixed.roc_auc"]
    if base["hi"] >= 0.9:
        bad.append("baseline AUC interval reaches 0.9: 'modest' no longer fits")
    for k in ("core", "extended", "anchored"):
        if m[f"diff_auc.{k}_minus_beneish"]["lo"] > 0:
            bad.append(f"{k} significantly beats the baseline: 'did not improve' is wrong")
        if m[f"{k}.roc_auc"]["estimate"] > base["estimate"] and k == "core":
            bad.append("core point estimate above baseline: 'best performer' wording needs review")
    if sig["benford_mad"]["lo"] > 0.5 or sig["benford_mad"]["estimate"] > 0.55:
        bad.append("Benford MAD separates groups: 'did not separate' is wrong")
    others = {k: d for k, d in sig.items() if k != "mscore" and not k.endswith("_ops")}
    if others[max(others, key=lambda k: others[k]["estimate"])]["lo"] > 0.5:
        bad.append("the best non-M-score signal is significantly above 0.5: 'no better than chance' is wrong")
    if (
        max(d["estimate"] for k, d in sig.items() if k != "mscore" and not k.endswith("_ops"))
        > sig["mscore"]["estimate"]
    ):
        bad.append("a single signal beats the M-score: 'M-score is best' is wrong")
    if results["holdout"]["metrics"]["beneish_fixed.roc_auc"]["lo"] > 0.5:
        bad.append("holdout confirms the M-score: the memo's 'does not generalise' wording must be rewritten")
    if results["holdout"]["metrics"]["diff_auc.core_minus_beneish"]["lo"] > 0:
        bad.append("frozen composite significantly beats the baseline on the holdout: wording must change")
    return bad


def render_all(root: Path) -> dict[Path, str]:
    """Render every document; returns {output path: text}. Used by render_docs and check_claims."""
    import json

    from .data_io import load_processed

    results = json.loads((root / "reports" / "results.json").read_text())
    problems = narrative_guards(results)
    if problems:
        raise ValueError("narrative assumptions violated:\n  " + "\n  ".join(problems))
    _, companies, cases = load_processed(root / "data" / "processed")
    outcomes = {
        "core": pd.read_csv(root / "reports/tables/case_outcomes_core.csv"),
        "beneish_fixed": pd.read_csv(root / "reports/tables/case_outcomes_beneish.csv"),
        "holdout_core": pd.read_csv(root / "reports/tables/holdout_outcomes_core.csv"),
        "holdout_beneish_fixed": pd.read_csv(root / "reports/tables/holdout_outcomes_beneish_fixed.csv"),
    }
    controls = pd.read_csv(root / "data/processed/controls.csv")
    excluded = pd.read_csv(root / "data/cases/excluded.csv")
    build_log = json.loads((root / "data/processed/build_log.json").read_text())
    values = build_values(results, outcomes, cases)
    values.update(case_doc_values(cases, controls, companies, excluded, build_log))
    targets = {
        "docs/templates/README.md.tpl": "README.md",
        "docs/templates/memo.md.tpl": "reports/memo.md",
        "docs/templates/CV_BULLETS.md.tpl": "CV_BULLETS.md",
        "docs/templates/case_selection.md.tpl": "docs/case_selection.md",
    }
    out = {}
    for tpl, dest in targets.items():
        text = (root / tpl).read_text()
        stray = stray_decimals(text)
        if stray:
            raise ValueError(f"{tpl}: hand-typed decimals {stray}; use a placeholder")
        out[root / dest] = render(text, values)
    return out
