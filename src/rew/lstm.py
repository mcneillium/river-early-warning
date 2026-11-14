"""A regional LSTM that reads the raw daily series (Experiment 6).

The boosting models see hand-built summaries of the last 90 days. This model
sees the last 365 days as they are: precipitation, temperature, potential
evapotranspiration and observed flow, plus the fixed catchment descriptors.
It forecasts flow 1, 3 and 7 days after the last day of that window and is
never shown weather from after it.

Everything is held as arrays of shape (catchment, day, variable) on one
shared calendar, so a training window is a slice and can be cut on the GPU.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from torch import nn

from rew.load import RECORD_END, RECORD_START
from rew.regional import STATIC_FEATURES
from rew.splits import assign_split

DYNAMIC = ("precip", "temp", "pet", "flow")
FLOW = DYNAMIC.index("flow")
WINDOW = 365
LEADS = (1, 3, 7)


@dataclass
class Panel:
    """Every catchment on one daily calendar."""

    gauges: list[str]
    dates: pd.DatetimeIndex
    dynamic: np.ndarray  # (catchment, day, 4); flow is log(1 + flow); NaN where missing
    static: np.ndarray  # (catchment, descriptor)
    split: np.ndarray  # (day,) "train", "validation", "test" or "" for each date

    def index_of(self, gauges) -> np.ndarray:
        position = {gauge: i for i, gauge in enumerate(self.gauges)}
        return np.array([position[gauge] for gauge in gauges], dtype=np.int64)


def build_panel(frames: dict[str, pd.DataFrame], attributes: pd.DataFrame, config: dict) -> Panel:
    dates = pd.date_range(RECORD_START, RECORD_END, freq="D")
    gauges = sorted(frames)
    dynamic = np.full((len(gauges), len(dates), len(DYNAMIC)), np.nan, dtype=np.float32)
    for i, gauge in enumerate(gauges):
        dynamic[i] = frames[gauge].reindex(dates)[list(DYNAMIC)].to_numpy(dtype=np.float32)
    dynamic[..., FLOW] = np.log1p(np.clip(dynamic[..., FLOW], 0.0, None))
    static = attributes.set_index("gauge_id").loc[gauges, STATIC_FEATURES].to_numpy(dtype=np.float32)
    split = assign_split(dates, config).astype("object").fillna("").to_numpy()
    return Panel(gauges, dates, dynamic, static, split)


@dataclass
class Scaler:
    dynamic_mean: np.ndarray
    dynamic_std: np.ndarray
    static_mean: np.ndarray
    static_std: np.ndarray


def fit_scaler(panel: Panel, train_catchments: np.ndarray) -> Scaler:
    """Means and standard deviations from the training catchments' training years only."""
    block = panel.dynamic[train_catchments][:, panel.split == "train"]
    flat = block.reshape(-1, block.shape[-1])
    static = panel.static[train_catchments]

    def safe(std: np.ndarray) -> np.ndarray:
        return np.where(np.isfinite(std) & (std > 0), std, 1.0).astype(np.float32)

    return Scaler(
        np.nanmean(flat, axis=0).astype(np.float32),
        safe(np.nanstd(flat, axis=0)),
        np.nanmean(static, axis=0).astype(np.float32),
        safe(np.nanstd(static, axis=0)),
    )


@dataclass
class Tensors:
    x: torch.Tensor  # (catchment, day, 5): four scaled variables and a missing-flow flag
    target: torch.Tensor  # (catchment, day + max lead): scaled log flow, NaN where missing or past the record
    static: torch.Tensor  # (catchment, descriptor), scaled


def to_tensors(panel: Panel, scaler: Scaler, device: torch.device | str) -> Tensors:
    scaled = (panel.dynamic - scaler.dynamic_mean) / scaler.dynamic_std
    flow_missing = np.isnan(scaled[..., FLOW])
    # A missing value becomes 0, the training mean. Flow also gets a flag.
    x = np.concatenate([np.nan_to_num(scaled, nan=0.0), flow_missing[..., None].astype(np.float32)], axis=-1)
    static = np.nan_to_num((panel.static - scaler.static_mean) / scaler.static_std, nan=0.0)
    # Padded with NaN so a target date past the end of the record reads as missing.
    target = np.pad(scaled[..., FLOW], ((0, 0), (0, max(LEADS))), constant_values=np.nan)
    return Tensors(
        torch.from_numpy(x).to(device),
        torch.from_numpy(target).to(device),
        torch.from_numpy(static.astype(np.float32)).to(device),
    )


def split_mask(panel: Panel, split: str) -> np.ndarray:
    """True for each date in `split`, padded with False past the end of the record."""
    return np.pad(panel.split == split, (0, max(LEADS)), constant_values=False)


def issue_days(panel: Panel, split: str, window: int = WINDOW) -> np.ndarray:
    """Issue days t whose window fits and with at least one target date in `split`."""
    days = np.arange(window - 1, len(panel.dates) - min(LEADS))
    in_split = split_mask(panel, split)
    wanted = np.zeros(len(days), dtype=bool)
    for lead in LEADS:
        wanted |= in_split[days + lead]
    return days[wanted]


def cut_windows(tensors: Tensors, catchment: torch.Tensor, day: torch.Tensor, window: int = WINDOW) -> torch.Tensor:
    """The `window` days ending on each issue day. Nothing after the issue day."""
    offsets = torch.arange(-window + 1, 1, device=day.device)
    return tensors.x[catchment[:, None], day[:, None] + offsets]


def cut_targets(
    tensors: Tensors, in_split: torch.Tensor, catchment: torch.Tensor, day: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Targets at each lead, and which of them may be used.

    A target is used only if it exists and its own date is in the split.
    """
    target_day = day[:, None] + torch.tensor(LEADS, device=day.device)
    y = tensors.target[catchment[:, None], target_day]
    mask = in_split[target_day] & ~torch.isnan(y)
    return torch.nan_to_num(y, nan=0.0), mask


class FlowLSTM(nn.Module):
    def __init__(self, n_dynamic: int, n_static: int, hidden: int = 256, dropout: float = 0.4):
        super().__init__()
        self.lstm = nn.LSTM(n_dynamic + n_static, hidden, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, len(LEADS))

    def forward(self, x: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        repeated = static[:, None, :].expand(-1, x.shape[1], -1)
        out, _ = self.lstm(torch.cat([x, repeated], dim=-1))
        return self.head(self.dropout(out[:, -1]))


def masked_mse(prediction: torch.Tensor, y: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    squared = (prediction - y) ** 2 * mask
    return squared.sum() / mask.sum().clamp(min=1)


@dataclass
class Settings:
    hidden: int = 256
    dropout: float = 0.4
    learning_rate: float = 1e-3
    batch: int = 2048
    epochs: int = 30
    windows_per_epoch: int = 2_000_000
    patience: int = 4
    validation_fraction: float = 0.2
    window: int = WINDOW  # days of history; 365 in Experiment 6
    weight_decay: float = 0.0  # 0 keeps plain Adam, as in Experiment 6; above 0 uses AdamW


def train(
    panel: Panel,
    tensors: Tensors,
    train_catchments: np.ndarray,
    settings: Settings,
    seed: int,
    log=print,
) -> tuple[FlowLSTM, list[dict]]:
    """Fit on the training years of `train_catchments`; stop on their validation years."""
    device = tensors.x.device
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    in_train = torch.from_numpy(split_mask(panel, "train")).to(device)
    in_valid = torch.from_numpy(split_mask(panel, "validation")).to(device)
    train_days = issue_days(panel, "train", settings.window)
    valid_days = issue_days(panel, "validation", settings.window)

    # The validation sample is fixed and does not depend on the model seed.
    valid_rng = np.random.default_rng(20261114)
    n_valid = int(settings.validation_fraction * len(train_catchments) * len(valid_days))
    valid_c = torch.from_numpy(valid_rng.choice(train_catchments, n_valid)).to(device)
    valid_d = torch.from_numpy(valid_rng.choice(valid_days, n_valid)).to(device)

    model = FlowLSTM(tensors.x.shape[-1], tensors.static.shape[-1], settings.hidden, settings.dropout).to(device)
    if settings.weight_decay > 0:
        optimiser = torch.optim.AdamW(model.parameters(), lr=settings.learning_rate, weight_decay=settings.weight_decay)
    else:
        optimiser = torch.optim.Adam(model.parameters(), lr=settings.learning_rate)

    def validation_loss() -> float:
        model.eval()
        total, count = 0.0, 0
        with torch.no_grad():
            for start in range(0, n_valid, settings.batch * 4):
                c, d = valid_c[start : start + settings.batch * 4], valid_d[start : start + settings.batch * 4]
                y, mask = cut_targets(tensors, in_valid, c, d)
                prediction = model(cut_windows(tensors, c, d, settings.window), tensors.static[c])
                total += float(((prediction - y) ** 2 * mask).sum())
                count += int(mask.sum())
        return total / max(count, 1)

    steps = max(1, settings.windows_per_epoch // settings.batch)
    best_loss, best_state, since_best, history = float("inf"), None, 0, []
    for epoch in range(1, settings.epochs + 1):
        started = time.time()
        model.train()
        running = 0.0
        for _ in range(steps):
            c = torch.from_numpy(rng.choice(train_catchments, settings.batch)).to(device)
            d = torch.from_numpy(rng.choice(train_days, settings.batch)).to(device)
            y, mask = cut_targets(tensors, in_train, c, d)
            loss = masked_mse(model(cut_windows(tensors, c, d, settings.window), tensors.static[c]), y, mask)
            optimiser.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            running += loss.item()
        valid = validation_loss()
        history.append({"epoch": epoch, "train_loss": running / steps, "validation_loss": valid,
                        "seconds": round(time.time() - started, 1)})
        log(f"  epoch {epoch:2d}  train {running / steps:.4f}  validation {valid:.4f}  "
            f"{history[-1]['seconds']:.0f}s")
        if valid < best_loss:
            best_loss, since_best = valid, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            since_best += 1
            if since_best >= settings.patience:
                break
    model.load_state_dict(best_state)
    return model, history


def predict(
    panel: Panel,
    tensors: Tensors,
    scaler: Scaler,
    model: FlowLSTM,
    catchments: np.ndarray,
    split: str = "test",
    batch: int = 8192,
    window: int = WINDOW,
) -> pd.DataFrame:
    """Forecasts in mm/day for every target date in `split`.

    Returns gauge_id, date (the target date), lead_days, forecast.
    """
    device = tensors.x.device
    days = issue_days(panel, split, window)
    in_split = split_mask(panel, split)
    model.eval()
    blocks = []
    with torch.no_grad():
        for catchment in catchments:
            outputs = []
            for start in range(0, len(days), batch):
                d = torch.from_numpy(days[start : start + batch]).to(device)
                c = torch.full_like(d, int(catchment))
                outputs.append(model(cut_windows(tensors, c, d, window), tensors.static[c]).float().cpu().numpy())
            scaled = np.concatenate(outputs)
            log_flow = scaled * scaler.dynamic_std[FLOW] + scaler.dynamic_mean[FLOW]
            flow = np.clip(np.expm1(log_flow), 0.0, None)
            for j, lead in enumerate(LEADS):
                keep = in_split[days + lead]
                blocks.append(pd.DataFrame({
                    "gauge_id": panel.gauges[int(catchment)],
                    "date": panel.dates[days[keep] + lead],
                    "lead_days": lead,
                    "forecast": flow[keep, j].astype(np.float32),
                }))
    return pd.concat(blocks, ignore_index=True)
