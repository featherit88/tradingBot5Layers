# indicators

**Purpose:** Calculates all technical indicators used by scoring and strategies.

## Public API

| Function | Description |
|---|---|
| `atr(df, period)` | Average True Range |
| `supertrend(df, atr_period, multiplier)` | Supertrend with direction (1=bull, -1=bear) |
| `market_structure_bullish(df)` | HH + HL detection via fractal swing points |
| `market_structure_bearish(df)` | LL + LH detection via fractal swing points |
| `heikin_ashi(df)` | Convert OHLC to Heikin-Ashi candles |
| `ha_signal_bullish(df, n)` | Last n HA candles are bullish |
| `ha_signal_bearish(df, n)` | Last n HA candles are bearish |
| `vwap(df)` | Session VWAP (df must be sliced to session start) |
| `volume_spike(df, mult, period)` | True if volume >= threshold and <= reject cap |
| `ema_ribbon(df, periods)` | Dict of EMA series keyed by period |
| `ema_ribbon_bullish(df)` | 5 > 8 > 13 EMA stack |
| `ema_ribbon_bearish(df)` | 5 < 8 < 13 EMA stack |

## Dependencies

- `config` — indicator parameter constants
