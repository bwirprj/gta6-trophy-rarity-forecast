# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/bwirprj/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/bwirprj/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecast every Grand Theft Auto VI PlayStation 5 trophy's Exophase earn rate at 2026-11-26T00:00:00Z, six and a half days after release, from the house's reads of the trophy page through the deadline. Five quantiles per trophy on the logit scale, scored by mean pinball loss.

The model reads earned counts instead of rates. Exophase prints `earned / tracked`, so each read yields an integer-ish count `k = rate / 100 * players_tracked`, which survives a refresh that only adds unearned players. `k` and the tracked count are extrapolated from the case's own history with a power law in hours since release, and the forecast rate is their ratio, so a growing denominator dilutes a trophy whose earners lag while a trophy on the early story line gains. The quantile spread adds the fit residual, the horizon and the counting noise of `k`.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` case in the input directory and writes `<id>.out` beside it: `{"trophies":[{"id":1,"q":[q05,q25,q50,q75,q95]}, ...]}` in percent, Python 3.13 standard library only, no network, deterministic.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
