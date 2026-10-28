"""Math behind Earnings Outlook.

Everything here runs on SAMPLE data. The idea: treat a creator's income the
way an actuary treats uncertain claims. Show a range instead of one number,
lean on similar experiences when your own history is thin (credibility),
and hold a reserve for the bad case.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

AS_OF = date(2026, 10, 28)       # fixed so every visitor sees the same numbers
DEVEX_MIN = 30_000               # Earned Robux needed to cash out (Roblox docs)
DEVEX_RATE = 0.0038              # USD per Earned Robux (Roblox docs)
WEEKEND_LIFT = 1.25              # Saturdays and Sundays run busier
STREAMS = {                      # share of revenue by source
    "Passes": 0.35,
    "Developer products": 0.30,
    "Subscriptions": 0.10,
    "Immersive ads": 0.10,
    "Creator Rewards": 0.15,
}

# What a typical similar experience does day to day (log change in players).
# A slight downward drift: most experiences fade without new updates.
PEER_DRIFT, PEER_VOL = -0.001, 0.06
# Credibility constant: with K days of history, your own data gets 50% weight.
K = 45

EXPERIENCES = {
    "Pet Pals Obby (new, 3 weeks old)": dict(
        days=21, start_dau=250, drift=0.03, vol=0.06, arpdau=1.5, balance=2_000),
    "Maple Street Roleplay (steady, 1 year)": dict(
        days=365, start_dau=1_300, drift=0.0004, vol=0.015, arpdau=1.2, balance=6_000),
    "Bloom Tycoon (viral spike)": dict(
        days=120, start_dau=600, drift=0.0, vol=0.04, arpdau=2.0, balance=4_000,
        spike_day=95, spike_size=2.3, decay=-0.04),
}


def _weekend(dates):
    return np.where(pd.DatetimeIndex(dates).dayofweek >= 5, WEEKEND_LIFT, 1.0)


def sample_history(name, seed=7):
    """Daily players and revenue for one sample experience."""
    p = EXPERIENCES[name]
    rng = np.random.default_rng(seed)
    n = p["days"]
    steps = p["drift"] + p["vol"] * rng.standard_normal(n)
    if "spike_day" in p:                       # a sudden viral jump, then a slow fade
        steps[p["spike_day"]] += p["spike_size"]
        steps[p["spike_day"] + 1:] += p["decay"]
    level = np.log(p["start_dau"]) + np.cumsum(steps)
    dates = [AS_OF - timedelta(days=n - 1 - i) for i in range(n)]
    dau = np.exp(level) * _weekend(dates)
    # spending per player wobbles a little day to day
    arpdau = p["arpdau"] * np.exp(0.05 * rng.standard_normal(n))
    df = pd.DataFrame({"date": pd.to_datetime(dates), "dau": dau.round()})
    for stream, share in STREAMS.items():
        df[stream] = (df["dau"] * arpdau * share * np.exp(0.08 * rng.standard_normal(n))).round()
    df["revenue"] = df[list(STREAMS)].sum(axis=1)
    return df


def credibility(history):
    """Blend your own trend with similar experiences', weighted Z = n / (n + K)."""
    n = len(history)
    window = history.tail(28)
    log_level = np.log(window["dau"] / _weekend(window["date"]))
    changes = np.diff(log_level)
    # Median and MAD instead of mean and std, so one viral day can't set the trend
    own_drift = np.median(changes)
    own_vol = 1.4826 * np.median(np.abs(changes - own_drift))
    z = n / (n + K)
    return dict(
        z=z,
        drift=z * own_drift + (1 - z) * PEER_DRIFT,
        vol=z * own_vol + (1 - z) * PEER_VOL,
    )


def project(history, horizon=90, paths=1000, seed=11):
    """Monte Carlo: simulate future players, turn them into revenue."""
    rng = np.random.default_rng(seed)
    cred = credibility(history)
    last = history.tail(28)
    arpdau = last["revenue"].sum() / last["dau"].sum()
    start = np.log(history["dau"].iloc[-1] / _weekend(history["date"].iloc[[-1]])[0])

    steps = cred["drift"] + cred["vol"] * rng.standard_normal((paths, horizon))
    future_dates = pd.date_range(history["date"].iloc[-1] + pd.Timedelta(days=1), periods=horizon)
    dau = np.exp(start + np.cumsum(steps, axis=1)) * _weekend(future_dates)
    revenue = dau * arpdau

    bands = pd.DataFrame({
        "date": future_dates,
        "low": np.percentile(revenue, 10, axis=0),
        "likely": np.percentile(revenue, 50, axis=0),
        "high": np.percentile(revenue, 90, axis=0),
    })
    totals = revenue.sum(axis=1)
    return dict(cred=cred, bands=bands, revenue=revenue, totals=totals,
                low=np.percentile(totals, 10), likely=np.percentile(totals, 50),
                high=np.percentile(totals, 90))


def payout_plan(revenue, balance, dates):
    """Chance of reaching the DevEx minimum, and the likely cash-out date."""
    running = balance + np.cumsum(revenue, axis=1)
    reached = running >= DEVEX_MIN
    chance_by_day = reached.mean(axis=0)               # share of paths there by each day
    # likely date = first day at least half of all futures have cashed out
    likely_day = np.argmax(chance_by_day >= 0.5) if chance_by_day[-1] >= 0.5 else None
    likely_date = dates[likely_day] if likely_day is not None else None
    return dict(chance_by_day=chance_by_day, likely_date=likely_date,
                chance_90=chance_by_day[-1])


def set_aside(outlook, tax_rate):
    """Reserve = estimated taxes on the likely case + a cushion for the low case."""
    taxes = tax_rate * outlook["likely"]
    cushion = outlook["likely"] - outlook["low"]
    return dict(taxes=taxes, cushion=cushion, total=taxes + cushion)


def what_changed(history):
    """Last 7 days vs the 7 before, split stepwise into 'more players' and 'more spending per player'."""
    prev, curr = history.iloc[-14:-7], history.iloc[-7:]
    dau0, dau1 = prev["dau"].sum(), curr["dau"].sum()
    rows = []
    for stream in STREAMS:
        rpd0, rpd1 = prev[stream].sum() / dau0, curr[stream].sum() / dau1
        rows.append({
            "stream": stream,
            "players effect": (dau1 - dau0) * rpd0,      # step 1: change players only
            "spending effect": dau1 * (rpd1 - rpd0),     # step 2: then change spending
        })
    out = pd.DataFrame(rows)
    out["total"] = out["players effect"] + out["spending effect"]
    return out


def early_alert(history):
    """Compare the last 7 days to the outlook we would have made a week ago."""
    past = project(history.iloc[:-7], horizon=7, paths=1000, seed=3)
    actual = history["revenue"].tail(7).sum()
    if actual < past["low"]:
        return "red", actual, past
    if actual < past["likely"]:
        return "amber", actual, past
    return "green", actual, past
