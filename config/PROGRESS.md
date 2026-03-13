# config — Progress

## Done
- All constants, enums, and instrument configs from CLAUDE.md spec
- Config validation: validate_config() checks score sum, risk ranges, drawdown ordering, volume thresholds, completeness (12 tests)
- Structured logging: setup_logging() with JSON format, log levels, file output (7 tests)

## In Progress
- Nothing

## Next
- Add per-instrument point value mapping (currently hardcoded in bot)
- Consider environment-based config overrides for paper vs live trading
