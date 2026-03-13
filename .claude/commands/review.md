Review the module specified by $ARGUMENTS against all project rules.

If no argument given, review ALL modules (config, indicators, filters, scoring, strategies, risk, broker, bot, backtest).

For each module, use a dedicated Agent to check:

1. **Datetime rules**: no `datetime.utcnow()`, naive datetimes coerced, time-gated features default OFF
2. **DataFrame safety**: `df.empty` guards before `iloc`, no `iloc[-n:0]`, division guards
3. **Multi-bar patterns**: different bars for different events, parametrized modes, TF agreement
4. **State ownership**: mutations inside owning method, no dead code, double-execution guards
5. **Error handling**: per-item try-except in loops, shutdown resilience
6. **Tracking**: equity curves every bar, all transitions logged to DB, real session boundaries
7. **Import hygiene**: no unused imports, imports from `__init__.py` only
8. **Test coverage**: every function has tests, tests assert behavior not types, realistic data

Report findings as a table:
| File | Line | Issue | Severity | Rule Violated |

Then offer to fix all issues found.
