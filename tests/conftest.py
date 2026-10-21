import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def example_row() -> pd.DataFrame:
    """One firm-year with round numbers so every Beneish index can be checked by hand."""
    return pd.DataFrame(
        [
            {
                "revenue": 1200.0,
                "revenue_prev": 1000.0,
                "cogs": 750.0,
                "cogs_prev": 600.0,
                "sga": 150.0,
                "sga_prev": 100.0,
                "dep": 45.0,
                "dep_prev": 50.0,
                "net_income": 120.0,
                "net_income_prev": 100.0,
                "cfo": 60.0,
                "cfo_prev": 90.0,
                "receivables": 180.0,
                "receivables_prev": 100.0,
                "current_assets": 500.0,
                "current_assets_prev": 400.0,
                "ppe": 320.0,
                "ppe_prev": 300.0,
                "total_assets": 1200.0,
                "total_assets_prev": 1000.0,
                "current_liabilities": 300.0,
                "current_liabilities_prev": 200.0,
                "lt_debt": 300.0,
                "lt_debt_prev": 200.0,
                "cash": 80.0,
                "cash_prev": 60.0,
                "debt_current": 20.0,
                "debt_current_prev": 10.0,
            }
        ]
    )


def synthetic_panel(seed: int = 0, n_case: int = 10, n_ctrl: int = 20) -> pd.DataFrame:
    """Panel where cases have shifted features, three labelled years per company."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_case + n_ctrl):
        is_case = i < n_case
        for year in (2012, 2013, 2014):
            shift = 1.0 if is_case else 0.0
            rows.append(
                {
                    "cik": 1000 + i,
                    "role": "case" if is_case else "control",
                    "fyear": year,
                    "case_id": f"c{i % n_case}",
                    "label": 1.0 if is_case else 0.0,
                    "filed": pd.Timestamp(year + 1, 3, 1),
                    "dsri": rng.normal(1 + 0.3 * shift, 0.3),
                    "gmi": rng.normal(1, 0.2),
                    "aqi": rng.normal(1 + 0.2 * shift, 0.3),
                    "sgi": rng.normal(1.1, 0.2),
                    "tata": rng.normal(0.05 * shift, 0.05),
                    "ar_rev_gap": rng.normal(0.1 * shift, 0.1),
                    "mscore": rng.normal(-2.3 + 0.8 * shift, 0.6),
                }
            )
    return pd.DataFrame(rows)
