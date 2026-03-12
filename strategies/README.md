# strategies

**Purpose:** Individual trade signal generators that detect entry opportunities.

## Public API

| Function | Timeframe | Description |
|---|---|---|
| `ema_ribbon_scalp(df_1m)` | 1M | 5/8/13 EMA stack, enter on 8 EMA pullback |
| `vwap_reversion(df_3m)` | 3M | Fade overextension from VWAP |
| `break_and_retest(df_5m, df_1m)` | 5M | Structure break, wait for retest |
| `opening_range_breakout(df_1m, bar_count)` | 1M | First 15-min range breakout |

Each function returns: `1` (long), `-1` (short), or `0` (no signal).

## Dependencies

- `config` — ORB_MINUTES
- `indicators` — EMA ribbon, VWAP
