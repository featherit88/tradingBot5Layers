# risk

**Purpose:** Position sizing, drawdown limits, and trade lifecycle management.

## Public API

| Export | Type | Description |
|---|---|---|
| `Trade` | dataclass | Represents an open trade (instrument, direction, entry, SL, TP, size) |
| `RiskManager` | class | Manages balance, open trades, sizing, drawdown checks |

### RiskManager methods

| Method | Description |
|---|---|
| `can_open_trade()` | Check max trades, daily/weekly drawdown limits |
| `daily_drawdown_hit()` | True if daily loss >= 3% |
| `weekly_drawdown_hit()` | True if weekly loss >= 6% |
| `position_size(entry, stop, point_value)` | Calculate size for 1% risk |
| `open_trade(trade)` | Register a new trade |
| `close_trade(trade, exit_price, pv)` | Close position, update balance, return PnL |
| `partial_close(trade, price, pv)` | Close 50% at 1R, return PnL |
| `reset_day()` / `reset_week()` | Reset drawdown baselines |

## Dependencies

- `config` — risk percentages, drawdown limits, max trades
