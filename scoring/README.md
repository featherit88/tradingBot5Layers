# scoring

**Purpose:** Confluence scoring system that decides if a signal is strong enough to trade.

## Public API

| Export | Type | Description |
|---|---|---|
| `ScoreBreakdown` | dataclass | Holds per-tool scores, exposes `.total` and `.triggered` |
| `compute_confluence(direction, df_5m, df_3m, df_1m)` | function | Score a trade direction across all 5 tools |

## Dependencies

- `config` — score weights, minimum threshold
- `indicators` — market structure, supertrend, HA, VWAP, volume spike
