# config

**Purpose:** Shared constants, enums, and instrument parameters for the entire bot.

## Public API

| Export | Type | Description |
|---|---|---|
| `Instrument` | Enum | US30, SPX |
| `Session` | Enum | LONDON, NEW_YORK |
| `InstrumentConfig` | dataclass | ATR floor, max spread, SL multiplier per instrument |
| `INSTRUMENT_CONFIGS` | dict | Instrument → InstrumentConfig mapping |
| `SESSION_WINDOWS` | dict | Session → (start, end) GMT time strings |
| `SCORE_*` | int | Point values for each confluence tool |
| `MIN_CONFLUENCE_SCORE` | int | Minimum score to trigger a trade (7) |
| `SUPERTREND_*` | float/int | Supertrend ATR period and multiplier |
| `EMA_PERIODS` | tuple | EMA ribbon periods (5, 8, 13) |
| `FRACTAL_BARS` | int | Market structure fractal bar count |
| `HEIKIN_ASHI_*` | int/float | HA candle count and max wick % |
| `VOLUME_*` | float/int | Volume spike/filter thresholds |
| `RISK_*` / `*_DRAWDOWN_*` | float | Risk and drawdown limits |
| `STARTING_CAPITAL` | float | Initial account balance (EUR) |
| `ORB_MINUTES` | int | Opening range duration |
| `NEWS_BUFFER_MINUTES` | int | News avoidance window |

## Dependencies

None — this is the base module with no imports from other project modules.
