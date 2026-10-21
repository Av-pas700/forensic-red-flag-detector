"""Load the committed, processed dataset (no network required)."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import config


def load_processed(path=config.DATA_PROCESSED):
    """Return ``(financials, companies, cases)`` from ``data/processed``."""
    fin = pd.read_csv(path / "financials.csv", parse_dates=["fye", "filed", "fye_prev"])
    companies = pd.read_csv(path / "companies.csv")
    cases = pd.read_csv(
        path / "cases_verified.csv",
        parse_dates=[
            "nonreliance_date",
            "first_signal_date",
            "enforcement_date",
            "bankruptcy_date",
            "cutoff",
        ],
    )
    cases["positive_fyears"] = (
        cases["positive_fyears"].astype(str).str.split(";").apply(lambda xs: [int(x) for x in xs])
    )
    return fin, companies, cases


def to_jsonable(obj):
    """Recursively convert numpy/pandas scalars to plain JSON types (NaN -> null)."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if math.isnan(obj) or math.isinf(obj) else float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.date().isoformat()
    return obj


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(obj), indent=2, sort_keys=True) + "\n")
