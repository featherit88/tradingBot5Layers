# SPX / US30 Scalping Bot

## Project Goal
Python scalping bot trading SPX and US30 indices.
Timeframes: 1M, 3M, 5M.
Starting capital: €2,000. Monthly profit target: €2,500.
Primary broker: IC Markets via cTrader API.

## Confluence Scoring System
A trade only fires when total score reaches 7 or more out of 10.

| Tool | Points | Timeframe | Key Config |
|---|---|---|---|
| Market Structure (HH+HL or LL+LH) | 3 | 5M + 3M | 3-bar fractal, 0.15% min swing, close confirmation only |
| Supertrend | 2 | 3M + 5M | ATR 10, multiplier 2.0, both TFs must agree |
| Heikin-Ashi | 2 | 3M | 3 candles, max 15% wick, doji = invalid |
| VWAP | 1 | 1M daily | NY session anchor 13:30 GMT, valid after 14:00 GMT only |
| Volume spike | 1 | 1M | >= 1.3x 20-bar avg, session-split baseline, reject if >3x |

## Entry Filters (all must pass before scoring)
- ATR(14) on 5M above 0.8 pts US30 / 2.5 pts SPX
- Volume above 1.2x 20-bar average
- No news event within 15 minutes
- Spread below 0.5 pts US30 / 0.4 pts SPX
- Session: London 07:00-10:00 GMT or NY 13:30-16:30 GMT only

## Risk Management
- Max risk per trade: 1% of account
- Max 2 trades open simultaneously
- Daily drawdown limit: 3% — bot halts for the day
- Weekly drawdown limit: 6% — manual review required
- Stop loss: 1.2x ATR14 on entry timeframe
- Take profit: close 50% at 1R, trail the rest

## Strategies
1. EMA Ribbon Scalp (1M) — 5/8/13 EMA stack, enter on 8 EMA pullback
2. VWAP Reversion (3M) — fade overextension, TP at VWAP reclaim
3. Break & Retest (5M) — structure break, wait for retest, enter with volume
4. Opening Range Breakout — first 15-min range at London/NY open

## Modular Architecture Rules

### Core Principle
One module = one domain responsibility. If you cannot describe the module in one sentence, split it.

### Module Structure
Every module MUST follow this folder layout:
```
module_name/
├── __init__.py      # Public API — what other modules import
├── core.py          # Main logic (or split into multiple files if needed)
├── README.md        # One-sentence purpose + public API reference
└── PROGRESS.md      # What's done, what's in progress, what's next
```

### Rules for When to Create a New Module
1. **Single Responsibility** — the module does exactly one thing for the architecture
2. **One-sentence test** — if you can't describe it in one sentence, split it
3. **Domain boundary** — different domain concerns never share a module
4. **Independence** — modules should minimize cross-dependencies; depend on interfaces, not internals
5. **No god modules** — if a module grows beyond ~300 lines of core logic, evaluate splitting

### Rules for Module Contents
- `__init__.py` exports ONLY the public API (functions, classes, constants other modules need)
- Internal helpers stay private (prefixed with `_` or kept in non-exported files)
- Each module's `README.md` must contain:
  - **Purpose**: one sentence
  - **Public API**: list of exported functions/classes with one-line descriptions
  - **Dependencies**: which other modules this one imports from
- Each module's `PROGRESS.md` must contain:
  - **Done**: completed features
  - **In Progress**: current work
  - **Next**: planned improvements

### Current Modules
| Module | One-sentence purpose |
|---|---|
| `config/` | Shared constants, enums, and instrument parameters |
| `indicators/` | Calculates all technical indicators used by scoring and strategies |
| `filters/` | Entry gates that must all pass before any signal is evaluated |
| `scoring/` | Confluence scoring system that decides if a signal is strong enough |
| `strategies/` | Individual trade signal generators |
| `risk/` | Position sizing, drawdown limits, and trade lifecycle management |
| `broker/` | Connection to cTrader API for market data and order execution |
| `bot/` | Main orchestration loop that ties all modules together |
| `backtest/` | Walk-forward simulation engine for strategy validation |

### Import Convention
```python
from config import Instrument, STARTING_CAPITAL
from indicators import atr, supertrend
from scoring import compute_confluence
```
Always import from the module's public API (`__init__.py`), never from internal files directly.

## Development Environment
- **Nothing runs on the Windows host** — all services run in Docker containers
- `docker compose -f docker/docker-compose.yml up` starts: Python bot container + MySQL container
- Source code is volume-mounted into the bot container for live reload
- All dependencies (Python, MySQL, etc.) are containerized

### CRITICAL: All Python Commands Run in Docker Only
**Never run `python`, `pytest`, `ruff`, or any Python command directly on the Windows host.**

#### Step 1: Start containers once per session
```bash
docker compose -f docker/docker-compose.yml up -d
```

#### Step 2: Use `exec` for all commands (instant, no startup overhead)
```bash
# Tests
docker compose -f docker/docker-compose.yml exec bot python -m pytest -v
docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_indicators.py -v
docker compose -f docker/docker-compose.yml exec bot python -m pytest tests/test_risk.py::TestTrailingStop -v

# Linting
docker compose -f docker/docker-compose.yml exec bot ruff check .

# Run bot / backtest
docker compose -f docker/docker-compose.yml exec bot python main.py
docker compose -f docker/docker-compose.yml exec bot python run_backtest.py

# Rebuild after adding dependencies to requirements.txt
docker compose -f docker/docker-compose.yml build bot && docker compose -f docker/docker-compose.yml up -d bot
```

#### Why `exec` not `run`
- `run --rm` creates a NEW container each time (~5-10s overhead)
- `exec` runs on the EXISTING container (instant, <1s)
- Source code is volume-mounted so edits are visible immediately

This applies to **all agents and subagents**.

## Current Status
Python bot skeleton is complete with modular architecture. Dockerized. Backtesting engine operational.
Next steps: implement real cTrader API calls in broker/, feed real historical data into backtest, trade logging to MySQL.

## TDD & Agile Workflow (MANDATORY)

**Every code change follows Test-Driven Development. No exceptions.**

### Batched TDD Cycle (per feature/module):
1. **UPDATE PROGRESS.md** — add planned work to "In Progress" (agents read this for context)
2. **PLAN** — list all functions needed, define inputs/outputs/edge cases for each
3. **WRITE ALL TESTS FIRST** — tests for every function in the batch, before any implementation
4. **WRITE ALL IMPLEMENTATIONS** — minimum code for the batch
5. **RUN TESTS & ITERATE** — fix failures, re-run until zero failures
6. **UPDATE DOCS** — move PROGRESS.md items to "Done", update README.md with final API

### Critical constraints:
- **PROGRESS.md before, README.md after** — plan goes in Progress first, API docs update after tests pass
- **Tests ALWAYS before implementation** — write all tests for the batch first, then implement
- **Iterate until zero failures** — do not move on with failing tests
- **Tests drive design** — if hard to test, the design is wrong, refactor
- **Agents must follow TDD too** — subagents read PROGRESS.md, write tests first
- **`docker-checks.sh` hook** runs syntax + ruff + tests automatically after every edit

### Example:
```
Task: Add drawdown tracking to risk/ (3 functions)

1. PROGRESS.md → "In Progress: daily/weekly drawdown checks + reset"
2. PLAN: check_daily_drawdown, check_weekly_drawdown, reset_tracking
3. WRITE ALL TESTS: 7 test methods covering happy path + edges + boundaries
4. WRITE ALL IMPLEMENTATIONS: 3 functions in risk/core.py
5. RUN → 2 failures → FIX → RUN → 0 failures ✓
6. PROGRESS.md → "Done: drawdown tracking", README.md → update API
```

## Development Rules (Lessons from Code Reviews)

These rules are derived from real bugs found across 4 review rounds. Follow them on every code change.

### Datetime & Timezone
- **Never use `datetime.utcnow()`** — always `datetime.now(timezone.utc)`
- **Always coerce naive datetimes to UTC** before comparing with aware datetimes. If a function receives a datetime, check `.tzinfo` and add `replace(tzinfo=timezone.utc)` if None
- **Time-gated features default to OFF** — if the current time is unknown (`None`), the feature must not fire. Use `if x is not None and condition` pattern, never `if x is None or condition`

### DataFrame & Pandas Safety
- **Check `df.empty` before any `iloc` access** — every function that receives a DataFrame must guard against empty input
- **Never use `iloc[-n:0]`** — this always returns an empty slice in pandas. Use positive index arithmetic: `start_idx = len(df) - n; df.iloc[start_idx:start_idx + m]`
- **Capture values before calling mutating methods** — if you need pre-mutation state (e.g., trade size before partial close), save it to a local variable first

### Math & Division
- **Guard all divisions** — check for zero or NaN denominators before dividing. For VWAP: replace zero cumulative volume with NaN. For percentage calculations: check `last_close == 0 or pd.isna(last_close)`

### Multi-Bar / Multi-Timeframe Patterns
- **Different bars for different events** — a break-and-retest requires the break on `iloc[-2]` and the retest on `iloc[-1]`, never both on the same bar
- **Parametrize filtering functions** — swing point detection must accept a `mode` parameter (high/low) so callers get only the swing type they need, not both mixed together
- **Both timeframes must agree** — when a rule says "5M + 3M must agree", check both independently and AND the results

### State Ownership & Mutation
- **Single source of truth** — state mutations (e.g., `trade.best_price = price`) belong inside the method that owns the state (e.g., `partial_close()`), not scattered across callers
- **Remove dead code after state changes** — if a trailing stop overwrites `stop_loss`, don't set `stop_loss` to breakeven right before it
- **Double-execution guard** — operations like `close_trade()` must check if already executed before applying side effects (PnL, balance changes)
- **Extract shared logic into one method** — if bot and backtest both compute trailing stops, put it in `risk.update_trailing_stop()` and call it from both

### Loop & Error Handling
- **Per-item try-except in loops** — one instrument failing must not crash the entire tick loop. Wrap each iteration body in try-except with `log.exception()`
- **Shutdown must be resilient** — wrap each trade close in its own try-except during shutdown so one failure doesn't skip remaining closes

### Tracking & Logging
- **Equity curves capture every bar** — append to equity curve on every loop iteration, not just on trade events. Add `equity_curve.append(balance)` before every `continue` statement
- **Log all state transitions to DB** — partial closes, full closes, and resets must all be persisted. Don't silently skip DB writes
- **Session tracking uses real boundaries** — use `check_session(now)` with actual session windows, never `hour // N` bucket heuristics
- **Reset accumulators on session/day boundaries** — counters like `_session_bar_counts` must be cleared in daily reset logic

### Testing Rules
- **Tests must assert behavior, not just types** — `assert isinstance(result, bool)` proves nothing. Assert `result is True` or `result is False` with data designed to produce that outcome
- **Test data must respect all thresholds** — if volume reject is 3x, don't use 5x in a spike test. Ensure test values are within valid operating ranges
- **Every code path needs a test** — if VWAP is blocked before 14:00, test both before and after. If direction can be 1 or -1, test both
- **Use realistic data shapes** — flat DataFrames for "no signal" cases, properly trending/zigzag data for "signal fires" cases

### Import Hygiene
- **Remove unused imports immediately** — don't leave `timezone` imported if only `time` is used. Clean up after every refactor
- **Import from `__init__.py` only** — never `from module.core import X`, always `from module import X`

## Decisions Already Made
- Supertrend: ATR 10 chosen over ATR 5 (ATR 5 too sensitive to single-candle spikes on US30)
- Supertrend multiplier: 2.0 not 3.0 (3.0 too slow for 3M scalping)
- Volume threshold: 1.3x not 1.5x (genuine scalp entries are only marginally above average)
- No RSI, MACD, Bollinger Bands or Stochastic (all excluded deliberately — see project notes)