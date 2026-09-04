"""SQLite schema and the migration ladder between its versions.

Kept apart from the store so that the shape of the database can be read in
one place, top to bottom, and so that a migration step is reviewed next to
the table it changes rather than buried in write logic.
"""

from __future__ import annotations

SCHEMA_VERSION = 4

_TRADES_TABLE = """
    CREATE TABLE trades (
        coin TEXT NOT NULL,
        trade_id INTEGER NOT NULL,
        event_time_ms INTEGER NOT NULL,
        side TEXT NOT NULL,
        price TEXT NOT NULL,
        size TEXT NOT NULL,
        tx_hash TEXT NOT NULL,
        buyer TEXT NOT NULL,
        seller TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (coin, trade_id)
    )
    """
_TRADES_INDEXES = (
    "CREATE INDEX trades_by_buyer ON trades (buyer)",
    "CREATE INDEX trades_by_seller ON trades (seller)",
)

_CANDLES_TABLE = """
    CREATE TABLE candles (
        coin TEXT NOT NULL,
        interval TEXT NOT NULL,
        open_time_ms INTEGER NOT NULL,
        close_time_ms INTEGER NOT NULL,
        open TEXT NOT NULL,
        high TEXT NOT NULL,
        low TEXT NOT NULL,
        close TEXT NOT NULL,
        volume TEXT NOT NULL,
        trade_count INTEGER NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (coin, interval, open_time_ms)
    )
    """

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE schema_version (
        version INTEGER NOT NULL PRIMARY KEY,
        applied_at_ms INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE wallets (
        address TEXT NOT NULL PRIMARY KEY,
        label TEXT,
        first_seen_at_ms INTEGER NOT NULL,
        last_seen_at_ms INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE fills (
        wallet_address TEXT NOT NULL,
        coin TEXT NOT NULL,
        trade_id INTEGER NOT NULL,
        event_time_ms INTEGER NOT NULL,
        side TEXT NOT NULL,
        price TEXT NOT NULL,
        size TEXT NOT NULL,
        fee TEXT NOT NULL,
        closed_pnl TEXT NOT NULL,
        start_position TEXT NOT NULL,
        direction TEXT NOT NULL,
        order_id INTEGER NOT NULL,
        crossed INTEGER NOT NULL,
        tx_hash TEXT NOT NULL,
        fee_token TEXT,
        raw_payload TEXT NOT NULL,
        source TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, coin, trade_id, event_time_ms)
    )
    """,
    "CREATE INDEX fills_by_wallet_time ON fills (wallet_address, event_time_ms)",
    """
    CREATE TABLE positions_snapshot (
        wallet_address TEXT NOT NULL,
        snapshot_time_ms INTEGER NOT NULL,
        account_value TEXT NOT NULL,
        total_notional_position TEXT NOT NULL,
        total_margin_used TEXT NOT NULL,
        withdrawable TEXT NOT NULL,
        open_position_count INTEGER NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, snapshot_time_ms)
    )
    """,
    """
    CREATE TABLE mids (
        coin TEXT NOT NULL,
        observed_at_ms INTEGER NOT NULL,
        mid TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (coin, observed_at_ms)
    )
    """,
    """
    CREATE TABLE funding (
        wallet_address TEXT NOT NULL,
        coin TEXT NOT NULL,
        event_time_ms INTEGER NOT NULL,
        usdc TEXT NOT NULL,
        funding_rate TEXT NOT NULL,
        signed_size TEXT NOT NULL,
        raw_payload TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (wallet_address, coin, event_time_ms)
    )
    """,
    """
    CREATE TABLE ingest_runs (
        run_id TEXT NOT NULL PRIMARY KEY,
        mode TEXT NOT NULL,
        wallet_address TEXT,
        started_at_ms INTEGER NOT NULL,
        finished_at_ms INTEGER,
        status TEXT NOT NULL,
        records_seen INTEGER NOT NULL DEFAULT 0,
        records_written INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        coverage TEXT
    )
    """,
    _TRADES_TABLE,
    *_TRADES_INDEXES,
    _CANDLES_TABLE,
)

#: Upgrades from one schema version to the next. A version with no entry here
#: cannot be opened: the guard fails closed rather than guessing at a shape.
_MIGRATIONS: dict[int, tuple[str, ...]] = {
    2: ("ALTER TABLE ingest_runs ADD COLUMN coverage TEXT",),
    3: (_TRADES_TABLE, *_TRADES_INDEXES),
    4: (_CANDLES_TABLE,),
}
