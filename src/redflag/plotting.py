"""Figures. Every plot is drawn from the same objects that produce results.json."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

from .benford import EXPECTED  # noqa: E402

PALETTE = {
    "beneish_fixed": "#7f7f7f",
    "beneish_p90": "#b0b0b0",
    "core": "#1b6ca8",
    "extended": "#d1495b",
    "anchored": "#2a9d8f",
    "case": "#d1495b",
    "control": "#1b6ca8",
    "neutral": "#9aa0a6",
}
LABELS = {
    "beneish_fixed": "Beneish M-score (baseline)",
    "core": "Composite (6 signals)",
    "extended": "Composite + Benford + NI-CFO gap",
    "anchored": "M-score + 3 signals (post hoc)",
    "beneish_p90": "Beneish (p90 cut-off)",
}

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "font.size": 9,
    }
)


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_roc_pr(ev: pd.DataFrame, scored: dict, results: dict, path: Path) -> Path:
    y = ev["label"].to_numpy().astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    for k in ("beneish_fixed", "core", "extended", "anchored"):
        s = scored[k].loc[ev.index, "score"].to_numpy()
        m = results["metrics"]
        a, p = m[f"{k}.roc_auc"], m[f"{k}.pr_auc"]
        fpr, tpr, _ = roc_curve(y, s)
        prec, rec, _ = precision_recall_curve(y, s)
        axes[0].plot(
            fpr,
            tpr,
            color=PALETTE[k],
            label=f"{LABELS[k]}: {a['estimate']:.2f} [{a['lo']:.2f}, {a['hi']:.2f}]",
        )
        axes[1].plot(
            rec,
            prec,
            color=PALETTE[k],
            label=f"{LABELS[k]}: {p['estimate']:.2f} [{p['lo']:.2f}, {p['hi']:.2f}]",
        )
    axes[0].plot([0, 1], [0, 1], ls=":", color="k", lw=0.8)
    axes[0].set(
        xlabel="False-positive rate", ylabel="True-positive rate", title="ROC (leave-one-company-out)"
    )
    axes[1].axhline(y.mean(), ls=":", color="k", lw=0.8)
    axes[1].set(
        xlabel="Recall",
        ylabel="Precision",
        title=f"Precision-recall (dotted = prevalence {y.mean():.2f} in this sample)",
    )
    for ax in axes:
        ax.legend(fontsize=7, loc="lower right" if ax is axes[0] else "upper right")
    return _save(fig, path)


def plot_case_timelines(panel: pd.DataFrame, scored: pd.DataFrame, cases: pd.DataFrame, path: Path) -> Path:
    n = len(cases)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(11, 2.5 * rows), squeeze=False)
    gap = scored["score"] - scored["threshold"]
    for ax, (_, c) in zip(axes.ravel(), cases.iterrows(), strict=False):
        d = panel[panel["cik"] == int(c["cik"])].sort_values("filed")
        g = gap.loc[d.index]
        mis = d["label"] == 1
        ax.axhline(0, color="k", lw=0.8)
        ax.plot(d["filed"], g, color=PALETTE["neutral"], lw=1)
        ax.scatter(d.loc[~mis, "filed"], g[~mis], s=18, color=PALETTE["neutral"], zorder=3)
        ax.scatter(d.loc[mis, "filed"], g[mis], s=26, color=PALETTE["case"], zorder=3)
        ax.axvline(c["nonreliance_date"], color="k", ls="--", lw=1)
        ax.set_title(c["company"], fontsize=8)
        locator = mdates.AutoDateLocator(maxticks=4)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.tick_params(labelsize=7)
        ax.set_xlim(d["filed"].min() - pd.Timedelta(days=120), c["nonreliance_date"] + pd.Timedelta(days=200))
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(
        "Composite score minus flag threshold at each 10-K (red = misstated year; dashed = Item 4.02 date)",
        fontsize=9,
    )
    return _save(fig, path)


def plot_lead_times(outcomes: dict[str, pd.DataFrame], path: Path) -> Path:
    core, base = outcomes["core"].set_index("case_id"), outcomes["beneish_fixed"].set_index("case_id")
    order = core["lead_years"].fillna(-1).sort_values().index
    fig, ax = plt.subplots(figsize=(7.5, 0.38 * len(order) + 1.2))
    ypos = np.arange(len(order))
    for off, (name, df, colour) in zip(
        (-0.18, 0.18),
        (("Composite", core, PALETTE["core"]), ("Beneish -1.78", base, PALETTE["beneish_fixed"])),
        strict=True,
    ):
        vals = df.loc[order, "lead_years"]
        ax.barh(ypos + off, vals.fillna(0), height=0.34, color=colour, label=name)
        for yp, det in zip(ypos + off, df.loc[order, "detected"], strict=True):
            if not det:
                ax.text(0.05, yp, "not flagged", va="center", fontsize=6.5, color=colour)
    ax.set_yticks(ypos, [core.loc[i, "company"] for i in order])
    ax.set_xlabel("Years between earliest flagged misstated-year 10-K and the cut-off date")
    ax.legend(fontsize=7)
    return _save(fig, path)


def plot_mscore(ev: pd.DataFrame, threshold: float, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    data = [ev.loc[ev["label"] == 0, "mscore"], ev.loc[ev["label"] == 1, "mscore"]]
    ax.boxplot(data, widths=0.45, showfliers=False, tick_labels=["Matched controls", "Misstated years"])
    rng = np.random.default_rng(0)
    for i, d in enumerate(data, start=1):
        ax.scatter(
            i + rng.normal(0, 0.05, len(d)),
            d,
            s=10,
            alpha=0.5,
            color=PALETTE["control"] if i == 1 else PALETTE["case"],
        )
    ax.axhline(threshold, color="k", ls="--", lw=1)
    ax.text(2.45, threshold, f"{threshold}", va="bottom", ha="right", fontsize=7)
    ax.set_ylabel("Beneish M-score")
    return _save(fig, path)


def plot_benford(ev: pd.DataFrame, path: Path) -> Path:
    cols = [f"bd{i}" for i in range(1, 10)]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    x = np.arange(1, 10)
    for lab, name, colour in (
        (1, "Misstated years", PALETTE["case"]),
        (0, "Matched controls", PALETTE["control"]),
    ):
        tot = ev.loc[ev["label"] == lab, cols].sum()
        axes[0].plot(x, tot.to_numpy() / tot.sum(), marker="o", color=colour, label=name)
    axes[0].plot(x, EXPECTED, color="k", ls="--", label="Benford")
    axes[0].set(
        xlabel="First digit", ylabel="Share of reported values", title="Pooled first-digit frequencies"
    )
    axes[0].legend(fontsize=7)
    axes[1].boxplot(
        [ev.loc[ev["label"] == 0, "benford_mad"], ev.loc[ev["label"] == 1, "benford_mad"]],
        widths=0.45,
        tick_labels=["Matched controls", "Misstated years"],
        showfliers=False,
    )
    for v, t in ((0.006, "close"), (0.012, "acceptable"), (0.015, "nonconformity >")):
        axes[1].axhline(v, color="k", ls=":", lw=0.7)
        axes[1].text(2.4, v, t, fontsize=6.5, ha="right", va="bottom")
    axes[1].set(ylabel="MAD per filing", title="Per-filing MAD (Nigrini bands)")
    return _save(fig, path)


def plot_single_signals(results: dict, path: Path) -> Path:
    sing = results["single_signals"]
    names = sorted(sing, key=lambda k: sing[k]["estimate"])
    fig, ax = plt.subplots(figsize=(6, 0.3 * len(names) + 1))
    est = np.array([sing[k]["estimate"] for k in names])
    lo = np.array([sing[k]["lo"] for k in names])
    hi = np.array([sing[k]["hi"] for k in names])
    ax.errorbar(
        est, np.arange(len(names)), xerr=[est - lo, hi - est], fmt="o", color=PALETTE["core"], capsize=2
    )
    ax.axvline(0.5, color="k", ls=":")
    ax.set_yticks(np.arange(len(names)), names)
    ax.set_xlabel("ROC-AUC of the raw signal (higher value = riskier); 95% cluster-bootstrap CI")
    return _save(fig, path)
