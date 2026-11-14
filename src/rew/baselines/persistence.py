"""Persistence: tomorrow will look like today.

The forecast for day d, issued `lead` days earlier, is simply the flow that
was observed on day d - lead. It has no parameters and needs no training.
Because rivers change slowly it is a strong baseline at short lead times, and
any model that cannot beat it is not worth the complexity.
"""

from __future__ import annotations

import pandas as pd


def predict(flow: pd.Series, lead: int) -> pd.Series:
    """Forecast indexed by target date. NaN where the issue-day flow is missing."""
    if lead < 1:
        raise ValueError("lead must be at least 1 day")
    return flow.shift(lead).rename("persistence")
