# gta6-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/poyobi/gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/poyobi/gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

**A launch-day Twitch viewer forecaster for Grand Theft Auto VI.** One hour into release day, it forecasts the "Grand Theft Auto VI" category's viewer count for each remaining hour (2-24, UTC) as five honest quantiles (5/25/50/75/95%).

## Method

The case's only scale anchor is hour 1's count. The case file itself carries dozens of comparable past launches with full hourly curves; the forecaster keeps only launches whose hour 1 was already live (rolling-midnight unlocks, GTA VI's own pattern — global-unlock games sit in dead air at 00:00 UTC and would poison the ratios), then reads each hour's quantiles off the empirical distribution of log(viewers_h / viewers_1), smoothed over hours with the tails lightly shrunk toward the hour's own spread. The resulting shape is the launch-day diurnal cycle: a decay to ~0.7x by the global trough, then a build to a ~1.4x evening peak. A calibrated fallback table covers cases with too few usable comparables.

Pure Python 3.13 standard library, deterministic, offline, runs in well under a second.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
