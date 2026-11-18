#!/usr/bin/env python3
"""GTA VI launch-day Twitch CCU forecaster (make.fun gta6-twitch-ccu-forecast-01).

Reads every case file in $MAKEFUN_INPUT_DIR (else /input) and, for each,
writes $MAKEFUN_OUTPUT_DIR/<id>.out with five quantiles (5/25/50/75/95%)
of the Twitch "Grand Theft Auto VI" category's hourly viewer count for
hours 2..24 of release day.

Method: the only honest anchor in a case is hour 1's count, p1. Past big
launches bundled in the case itself (comparables) show how a launch day
evolves relative to its own hour 1 - but only launches whose hour 1 was
already live (rolling midnight unlocks, like GTA VI) are comparable:
global-unlock games sit in dead air at 00:00 UTC and explode by 100x,
which would poison the ratios. So we keep comparables whose hour 1 is at
least a quarter of their day's peak, take the empirical distribution of
log(viewers_h / viewers_1) per hour, and read the five quantiles off it.
Pure standard library, deterministic, offline.
"""
import json
import math
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.645, -0.674, 0.0, 0.674, 1.645)

# Fallback ratios (quantiles of viewers_h / viewers_1) calibrated from 24
# comparable launches whose hour 1 was already live; used only if a case
# carries too few usable comparables.
FALLBACK = {
    2: (0.70, 0.82, 0.89, 1.00, 1.30), 3: (0.48, 0.66, 0.71, 0.91, 1.15),
    4: (0.42, 0.52, 0.70, 0.83, 0.99), 5: (0.38, 0.62, 0.75, 0.84, 1.08),
    6: (0.37, 0.55, 0.78, 0.99, 1.27), 7: (0.36, 0.51, 0.69, 0.99, 1.25),
    8: (0.39, 0.54, 0.66, 0.95, 1.24), 9: (0.39, 0.48, 0.69, 0.94, 1.31),
    10: (0.42, 0.48, 0.67, 0.94, 1.30), 11: (0.40, 0.50, 0.71, 0.95, 1.33),
    12: (0.42, 0.52, 0.84, 1.00, 1.48), 13: (0.51, 0.61, 0.91, 1.12, 1.91),
    14: (0.57, 0.68, 0.97, 1.30, 2.26), 15: (0.63, 0.76, 1.11, 1.53, 2.57),
    16: (0.69, 0.83, 1.17, 1.69, 2.71), 17: (0.76, 0.95, 1.28, 1.81, 2.59),
    18: (0.81, 0.98, 1.36, 1.98, 2.63), 19: (0.86, 0.99, 1.37, 2.13, 3.28),
    20: (0.84, 1.02, 1.41, 2.28, 3.15), 21: (0.87, 1.14, 1.46, 2.27, 3.08),
    22: (0.86, 1.02, 1.49, 2.21, 3.04), 23: (0.76, 1.03, 1.20, 2.12, 2.78),
    24: (0.71, 0.94, 1.17, 1.94, 2.56),
}


def parse_ts(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def hour_key(day_start, hour):
    return (day_start + timedelta(hours=hour - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def quantile(sorted_vals, p):
    """Type-7 empirical quantile with linear interpolation."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = p * (n - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def comparable_day(comp):
    """Return {hour: viewers} for hours 1..24 of a comparable, or None."""
    try:
        start = parse_ts(comp["day_start"])
    except Exception:
        return None
    by_from = {}
    for point in comp.get("hourly") or []:
        try:
            by_from[point["from"]] = float(point["viewers"])
        except Exception:
            continue
    day = {}
    for hour in range(1, 25):
        val = by_from.get(hour_key(start, hour))
        if val is None or val <= 0:
            return None
        day[hour] = val
    return day


def usable_comparables(case, min_share):
    days = []
    for comp in case.get("comparables") or []:
        name = (comp.get("name") or "").lower()
        unlock = comp.get("unlock") or ""
        if "before release" in name or unlock.startswith("Not a launch"):
            continue  # the pre-release GTA VI category: no launch day at all
        day = comparable_day(comp)
        if day is None:
            continue
        v1 = day[1]
        peak = max(day.values())
        if v1 >= 1000 and v1 >= min_share * peak:
            days.append(day)
    return days


def forecast_rows(case):
    p1 = 1.0
    for row in case.get("known") or []:
        if row.get("hour") == 1:
            p1 = max(1.0, float(row["viewers"]))
    days = usable_comparables(case, 0.25)
    if len(days) < 8:
        days = usable_comparables(case, 0.15)
    rows = []
    if len(days) >= 3:
        # Per-hour empirical log-ratio quantiles for each level.
        curves = {p: [] for p in LEVELS}
        medians, sds = [], []
        for hour in range(2, 25):
            logs = sorted(math.log(day[hour] / day[1]) for day in days)
            mean = sum(logs) / len(logs)
            var = sum((x - mean) ** 2 for x in logs) / len(logs)
            medians.append(quantile(logs, 0.5))
            sds.append(min(max(math.sqrt(var), 0.20), 0.55))
            for p in LEVELS:
                curves[p].append(quantile(logs, p))
        # Smooth each level's curve over hours (1-2-1) to kill small-n
        # jitter, then shrink the tails slightly toward a normal shape
        # with the hour's own spread: insurance against sampling noise
        # in the 5% and 95% quantiles of ~24 launches.
        for p, z in zip(LEVELS, Z):
            vals = curves[p]
            smooth = []
            for i, v in enumerate(vals):
                if 0 < i < len(vals) - 1:
                    smooth.append(0.25 * vals[i - 1] + 0.5 * v + 0.25 * vals[i + 1])
                else:
                    smooth.append(v)
            curves[p] = [
                0.85 * v + 0.15 * (medians[i] + z * sds[i]) if z != 0.0 else v
                for i, v in enumerate(smooth)
            ]
        for idx, hour in enumerate(range(2, 25)):
            qs = [curves[p][idx] for p in LEVELS]
            rows.append((hour, [p1 * math.exp(q) for q in qs]))
    else:
        for hour in range(2, 25):
            rows.append((hour, [p1 * r for r in FALLBACK[hour]]))
    out = []
    for hour, qs in rows:
        qs = sorted(qs)
        qs[2] = min(max(qs[2], 0.40 * p1), 3.0 * p1)   # median ratio clamp
        qs[0] = max(qs[0], 0.15 * p1)                    # floor for q05
        qs[4] = min(qs[4], 6.0 * p1)                     # cap for q95
        qs = sorted(qs)
        qs = [min(max(q, 1e-9), 1e9) for q in qs]
        out.append({"hour": hour, "q": [round(q, 2) for q in qs]})
    return out


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for name in names:
        with open(os.path.join(in_dir, name), encoding="utf-8") as fh:
            case = json.load(fh)
        case_id = case.get("id") or name[:-3]
        payload = {"hours": forecast_rows(case)}
        with open(os.path.join(out_dir, case_id + ".out"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
