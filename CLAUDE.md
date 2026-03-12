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

## Current Status
Python bot skeleton is complete with modular architecture. Dockerized. Backtesting engine operational.
Next steps: implement real cTrader API calls in broker/, add news feed integration, feed real historical data into backtest.

## Decisions Already Made
- Supertrend: ATR 10 chosen over ATR 5 (ATR 5 too sensitive to single-candle spikes on US30)
- Supertrend multiplier: 2.0 not 3.0 (3.0 too slow for 3M scalping)
- Volume threshold: 1.3x not 1.5x (genuine scalp entries are only marginally above average)
- No RSI, MACD, Bollinger Bands or Stochastic (all excluded deliberately — see project notes)