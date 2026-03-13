-- Auto-runs on first MySQL container start (empty db_data volume)
CREATE TABLE IF NOT EXISTS trades (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    opened_at       DATETIME NOT NULL,
    closed_at       DATETIME DEFAULT NULL,
    instrument      VARCHAR(20) NOT NULL,
    direction       TINYINT NOT NULL COMMENT '1=long, -1=short',
    strategy        VARCHAR(40) NOT NULL,
    score           TINYINT NOT NULL,
    entry_price     DOUBLE NOT NULL,
    exit_price      DOUBLE DEFAULT NULL,
    stop_loss       DOUBLE NOT NULL,
    take_profit_1r  DOUBLE NOT NULL,
    size            DOUBLE NOT NULL,
    pnl             DOUBLE DEFAULT NULL,
    exit_reason     VARCHAR(30) DEFAULT NULL,
    balance_after   DOUBLE DEFAULT NULL,
    partial_closed_at DATETIME DEFAULT NULL,
    partial_exit_price DOUBLE DEFAULT NULL,
    partial_pnl     DOUBLE DEFAULT NULL,
    remaining_size  DOUBLE DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_instrument (instrument),
    INDEX idx_opened (opened_at),
    INDEX idx_strategy (strategy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS daily_summary (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    trade_date      DATE NOT NULL UNIQUE,
    starting_balance DOUBLE NOT NULL,
    ending_balance  DOUBLE NOT NULL,
    total_trades    INT NOT NULL DEFAULT 0,
    wins            INT NOT NULL DEFAULT 0,
    losses          INT NOT NULL DEFAULT 0,
    total_pnl       DOUBLE NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
