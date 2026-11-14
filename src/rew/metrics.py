"""Scores for forecasts of river flow and for warnings derived from them.

Every function takes plain NumPy arrays that are already aligned and free of
NaN. Dropping missing pairs is the caller's job, so that all models can be
scored on exactly the same days.

Flow scores
    nse       Nash-Sutcliffe efficiency. 1 is perfect; 0 means no better than
              always forecasting the observed mean; negative is worse than that.
    kge_2009  Kling-Gupta efficiency, original form (Gupta et al., 2009).
              1 is perfect. Combines correlation, variability ratio and bias.

Warning scores (from a 2 x 2 table of forecast event against observed event)
    hit_rate           hits / (hits + misses)           share of events warned
    false_alarm_ratio  false alarms / (hits + false alarms)  share of warnings wrong
    csi                hits / (hits + misses + false alarms)  critical success index

Onset days
    The first day of an event: the event is observed today and was observed
    NOT to be happening yesterday. Flow changes slowly, so "same as today"
    forecasts score well on days when an event is already under way but can
    never anticipate a start. Scoring onset days separately shows whether a
    model gives any real early warning.
"""

from __future__ import annotations

import numpy as np


def _check(obs: np.ndarray, sim: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    if obs.shape != sim.shape:
        raise ValueError("obs and sim must have the same shape")
    if np.isnan(obs).any() or np.isnan(sim).any():
        raise ValueError("NaN in input: drop missing pairs before scoring")
    return obs, sim


def nse(obs: np.ndarray, sim: np.ndarray) -> float:
    obs, sim = _check(obs, sim)
    if obs.size == 0:
        return float("nan")
    spread = np.sum((obs - obs.mean()) ** 2)
    if spread == 0:
        return float("nan")
    return float(1.0 - np.sum((sim - obs) ** 2) / spread)


def kge_2009(obs: np.ndarray, sim: np.ndarray) -> float:
    obs, sim = _check(obs, sim)
    if obs.size < 2 or obs.std() == 0 or sim.std() == 0 or obs.mean() == 0:
        return float("nan")
    r = np.corrcoef(obs, sim)[0, 1]
    alpha = sim.std() / obs.std()
    beta = sim.mean() / obs.mean()
    return float(1.0 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def contingency(obs_event: np.ndarray, fc_event: np.ndarray) -> dict[str, int]:
    """Counts of hits, misses, false alarms and correct negatives."""
    obs_event = np.asarray(obs_event, dtype=bool)
    fc_event = np.asarray(fc_event, dtype=bool)
    if obs_event.shape != fc_event.shape:
        raise ValueError("obs_event and fc_event must have the same shape")
    return {
        "hits": int(np.sum(obs_event & fc_event)),
        "misses": int(np.sum(obs_event & ~fc_event)),
        "false_alarms": int(np.sum(~obs_event & fc_event)),
        "correct_negatives": int(np.sum(~obs_event & ~fc_event)),
    }


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def hit_rate(table: dict[str, int]) -> float:
    return _ratio(table["hits"], table["hits"] + table["misses"])


def false_alarm_ratio(table: dict[str, int]) -> float:
    return _ratio(table["false_alarms"], table["hits"] + table["false_alarms"])


def csi(table: dict[str, int]) -> float:
    return _ratio(table["hits"], table["hits"] + table["misses"] + table["false_alarms"])


def onset_mask(event_today: np.ndarray, event_yesterday: np.ndarray) -> np.ndarray:
    """True where an event starts.

    `event_yesterday` must be 1.0 (event), 0.0 (no event) or NaN (unknown, for
    example a gap in the flow record). A day counts as an onset only when
    yesterday is known to be event-free, so a gap never creates a false onset.
    """
    event_today = np.asarray(event_today, dtype=bool)
    event_yesterday = np.asarray(event_yesterday, dtype=float)
    return event_today & (event_yesterday == 0.0)


def onset_hit_rate(
    event_today: np.ndarray,
    event_yesterday: np.ndarray,
    fc_event: np.ndarray,
) -> tuple[float, int]:
    """Share of onset days that were forecast as events, and the number of onsets."""
    onsets = onset_mask(event_today, event_yesterday)
    count = int(onsets.sum())
    if count == 0:
        return float("nan"), 0
    return float(np.asarray(fc_event, dtype=bool)[onsets].mean()), count
