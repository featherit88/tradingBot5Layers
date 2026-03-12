# filters

**Purpose:** Entry gates that must all pass before any trade signal is evaluated.

## Public API

| Function | Description |
|---|---|
| `all_filters_pass(df_5m, df_1m, instrument, spread, now, news)` | Run all 5 filters, returns (passed, session) |
| `check_atr_floor(df_5m, instrument)` | ATR(14) above instrument minimum |
| `check_volume_floor(df)` | Volume above 1.2x 20-bar average |
| `check_spread(spread, instrument)` | Spread below instrument max |
| `check_session(now_gmt)` | Returns active Session or None |
| `check_news(now_gmt, news_times)` | True if no news within 15 min |

## Dependencies

- `config` — thresholds, instrument configs, session windows
- `indicators` — ATR calculation
