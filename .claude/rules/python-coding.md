---
paths:
  - "**/*.py"
---

# Python Coding Rules

## Datetime
- Never `datetime.utcnow()` — always `datetime.now(timezone.utc)`
- Coerce naive datetimes: `if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`
- Time-gated features default OFF: `if x is not None and condition` (never `if x is None or`)

## DataFrame & Pandas
- Check `df.empty` before any `iloc` access
- Never `iloc[-n:0]` — use positive arithmetic: `start = len(df) - n; df.iloc[start:start+m]`
- Capture values before mutating methods (e.g., save `trade.size` before `partial_close()`)
- Guard all divisions against zero/NaN

## Multi-Bar Patterns
- Different bars for different events (break on `iloc[-2]`, retest on `iloc[-1]`)
- Parametrize filtering (swing detection accepts `mode="high"/"low"`)
- Both timeframes must independently agree (AND results)
- Session tracking uses `check_session(now)`, never `hour // N`

## State & Error Handling
- State mutations belong inside the owning method (single source of truth)
- Remove dead code after state changes
- Double-execution guard on close/remove operations
- Extract shared logic (bot + backtest → one method in risk)
- Per-item try-except in loops (one failure doesn't crash the loop)
- Equity curves capture every bar, not just trade events
- Log all state transitions to DB

## Imports
- Remove unused imports immediately
- Import from `__init__.py` only — never `from module.core import X`
