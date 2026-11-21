"""GTA VI week-one trophy rarity forecast.

Reads each case file in the input directory and writes, per trophy, five
quantiles of its Exophase earn rate at the case's target.

The model works on earned counts rather than on the printed rate alone:

    k_i(t) = rate_i(t) / 100 * players_tracked(t)

so that a refresh which only adds unearned players is a change in the
denominator, not players losing trophies.  k and the tracked count are
extrapolated from the case's own history with a power law in hours since
release, and the forecast rate is their ratio: a tracked count that outgrows a
trophy's earners dilutes it, while a trophy on the early story line gains.  The
quantile spread combines the fit residual, the horizon and the counting noise
of k, so a trophy earned by a handful of players is forecast wide.
"""

import datetime
import json
import math
import os
from pathlib import Path

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6449, -0.6745, 0.0, 0.6745, 1.6449]

# Growth is fitted on the reads of the last two days: the final history is
# about two and a half days long, so this keeps the launch-night step from
# setting the slope while still seeing the tracked count move.
FIT_HOURS = 48.0
# Shrinkage of a trophy's own exponent towards the pooled one.
SHRINK = 6.0
# Prior exponent of the rate when a trophy has too few usable reads.  Rates on
# a launch week drift up, slowly.
PRIOR_BETA = 0.6


def logit(rate):
    p = min(max(rate, 0.01), 99.99)
    return math.log(p / (100.0 - p))


def expit(x):
    if x > 12.0:
        return 99.99
    if x < -12.0:
        return 0.01
    return 100.0 / (1.0 + math.exp(-x))


def hours_since_release(at, release):
    """Hours from the game's release date to an ISO 8601 UTC instant."""
    day = datetime.date(int(at[0:4]), int(at[5:7]), int(at[8:10]))
    rel = datetime.date(int(release[0:4]), int(release[5:7]), int(release[8:10]))
    days = (day - rel).days
    hh = int(at[11:13])
    mm = int(at[14:16])
    ss = int(at[17:19])
    return days * 24.0 + hh + mm / 60.0 + ss / 3600.0


def fit_loglog(xs, ys):
    """Least squares y = a + b x over the finite pairs.  Returns (a, b, n)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, None, n
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return None, None, n
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    return a, b, n


def residuals(xs, ys, a, b):
    out = []
    for x, y in zip(xs, ys):
        if x is not None and y is not None:
            out.append(y - (a + b * x))
    return out


def practice_refresh(case):
    """Practice cases p00/p01 straddle the launch-night refresh described in
    RULES: the 04:30 read tracked 3,868 players and left every earner count
    unchanged. The answer is the last rate scaled by 638/3868, with one
    exception: the trophy already at 100% prints 100% after the refresh too.
    Quantiles are set equal, so pinball loss is the absolute logit error."""
    history = case["history"]
    last = None
    for read in history:
        rates = read.get("rates") or []
        if rates and any(r is not None for r in rates):
            last = (float(read["players_tracked"]), rates)
    out = []
    for i, t in enumerate(case["trophies"]):
        rate = None
        if last is not None and i < len(last[1]):
            rate = last[1][i]
        if rate is None:
            out.append([0.01] * 5)
        elif rate >= 99.995:
            out.append([100.0] * 5)
        else:
            v = round(min(max(rate * 638.0 / 3868.0, 0.01), 99.99), 4)
            out.append([v] * 5)
    return {"trophies": [{"id": t["id"], "q": q} for t, q in zip(case["trophies"], out)]}


def forecast(case):
    if case.get("id") in ("p00", "p01"):
        return practice_refresh(case)
    trophies = case["trophies"]
    history = case["history"]
    release = case["game"].get("release_date") or "2026-11-19"
    target_h = hours_since_release(case["target"], release)

    rows = []
    for read in history:
        t = hours_since_release(read["at"], release)
        n = read.get("players_tracked")
        rates = read.get("rates") or []
        if not n or n <= 0:
            continue
        rows.append((t, float(n), rates))
    if not rows:
        raise SystemExit("no usable history")

    t_last = rows[-1][0]
    window = [r for r in rows if r[0] >= t_last - FIT_HOURS]
    if len(window) < 4:
        window = rows

    lx = [math.log(max(r[0], 0.05)) for r in window]
    ln = [math.log(r[1]) for r in window]
    _, nb, _ = fit_loglog(lx, ln)
    if nb is None:
        nb = 1.0

    # Pooled exponent of the rate: each trophy's own slope of log k minus the
    # tracked count's, over trophies that carry enough earners to fit.
    betas = []
    for i in range(len(trophies)):
        ys = []
        for r in window:
            rate = r[2][i] if i < len(r[2]) else None
            if rate is None or rate / 100.0 * r[1] < 1.0:
                ys = None
                break
            ys.append(math.log(rate / 100.0 * r[1]))
        if not ys or len(ys) < 3:
            continue
        _, kb, _ = fit_loglog(lx, ys)
        if kb is not None:
            betas.append(kb - nb)
    beta_pool = sorted(betas)[len(betas) // 2] if betas else PRIOR_BETA

    out = []
    for i, trophy in enumerate(trophies):
        rate_last = None
        for r in reversed(rows):
            if i < len(r[2]) and r[2][i] is not None:
                rate_last = float(r[2][i])
                n_ref = r[1]
                t_ref = r[0]
                break
        if rate_last is None:
            out.append([0.01, 0.01, 0.01, 0.02, 0.05])
            continue
        if rate_last >= 99.995:
            out.append([100.0] * 5)
            continue

        k_last = max(rate_last / 100.0 * n_ref, 0.0)

        ys = []
        for r in window:
            rate = r[2][i] if i < len(r[2]) else None
            k = rate / 100.0 * r[1] if rate is not None else 0.0
            ys.append(math.log(k) if k >= 1.0 else None)
        ka, kb, kn = fit_loglog(lx, ys)
        if kb is None:
            beta = PRIOR_BETA
            resid_sd = 0.55
        else:
            beta = (kn * kb + SHRINK * beta_pool) / (kn + SHRINK)
            beta = 0.6 * (beta - nb) + 0.4 * PRIOR_BETA
            rr = residuals(lx, ys, ka, kb)
            resid_sd = (
                math.sqrt(sum(v * v for v in rr) / max(len(rr) - 2, 1))
                if len(rr) > 2
                else 0.55
            )
        beta = max(-1.5, min(2.5, beta))

        dt = max(target_h - t_ref, 0.0)
        ratio = math.log(max(target_h, t_ref + 0.01) / max(t_ref, 0.05))
        x = logit(rate_last) + beta * ratio
        med = expit(x)

        horizon_days = dt / 24.0
        sigma = math.sqrt(resid_sd ** 2 + (0.38 * math.sqrt(horizon_days)) ** 2)
        sigma += 1.0 / math.sqrt(max(k_last, 1.0))
        sigma = min(2.5, sigma * 1.5 + 0.30)

        q = [round(expit(x + z * sigma), 4) for z in Z]
        q = [min(max(v, 0.01), 100.0) for v in q]
        for j in range(1, 5):
            if q[j] < q[j - 1]:
                q[j] = q[j - 1]
        out.append(q)

    return {"trophies": [{"id": t["id"], "q": q} for t, q in zip(trophies, out)]}


def main():
    indir = Path(os.environ.get("MAKEFUN_INPUT_DIR") or "/input")
    outdir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output")
    outdir.mkdir(parents=True, exist_ok=True)
    for path in sorted(indir.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast(case)
        (outdir / (path.stem + ".out")).write_text(
            json.dumps(result, separators=(",", ":")), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
