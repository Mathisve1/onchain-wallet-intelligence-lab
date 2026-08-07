from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

ZERO_HASH = "0" * 64


class StoreError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decimal(value: Any, label: str, *, nonnegative: bool = True) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise StoreError(f"{label}:invalid_decimal") from exc
    if not result.is_finite():
        raise StoreError(f"{label}:nonfinite")
    if nonnegative and result < 0:
        raise StoreError(f"{label}:negative")
    return result


class DurableStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=FULL")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._tx() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS system_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                execution_state TEXT NOT NULL,
                kill_switch INTEGER NOT NULL CHECK (kill_switch IN (0,1)),
                updated_at_ms INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO system_state(id, execution_state, kill_switch, updated_at_ms)
            VALUES (1, 'RESEARCH_ONLY', 1, 0);

            CREATE TABLE IF NOT EXISTS signers (
                signer_id TEXT PRIMARY KEY,
                public_address TEXT NOT NULL UNIQUE,
                environment TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
                created_at_ms INTEGER NOT NULL,
                revoked_at_ms INTEGER
            );

            CREATE TABLE IF NOT EXISTS nonce_state (
                signer_id TEXT PRIMARY KEY REFERENCES signers(signer_id),
                last_nonce INTEGER NOT NULL CHECK (last_nonce >= 0)
            );

            CREATE TABLE IF NOT EXISTS permits (
                permit_id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL UNIQUE,
                signer_id TEXT NOT NULL REFERENCES signers(signer_id),
                account_address TEXT NOT NULL,
                action_type TEXT NOT NULL,
                instrument TEXT NOT NULL,
                decision_mode TEXT NOT NULL,
                intent_sha256 TEXT NOT NULL,
                compiled_action_sha256 TEXT NOT NULL,
                strategy_version_hash TEXT NOT NULL,
                model_version_hash TEXT,
                policy_version_hash TEXT NOT NULL,
                data_snapshot_hash TEXT NOT NULL,
                risk_snapshot_hash TEXT NOT NULL,
                nonce INTEGER NOT NULL,
                issued_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                cloid TEXT,
                target_cloid TEXT,
                state TEXT NOT NULL CHECK (state IN ('ISSUED','CONSUMED','EXPIRED','REVOKED')),
                permit_json TEXT NOT NULL,
                UNIQUE(signer_id, nonce)
            );

            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                permit_id TEXT NOT NULL UNIQUE REFERENCES permits(permit_id),
                action_type TEXT NOT NULL,
                instrument TEXT NOT NULL,
                risk_increasing INTEGER NOT NULL CHECK (risk_increasing IN (0,1)),
                expected_quantity TEXT NOT NULL,
                filled_quantity TEXT NOT NULL DEFAULT '0',
                state TEXT NOT NULL,
                action_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS owned_orders (
                order_ref TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                cloid TEXT NOT NULL UNIQUE,
                terminal INTEGER NOT NULL CHECK (terminal IN (0,1)),
                updated_at_ms INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                timestamp_ms INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                action_id TEXT,
                permit_id TEXT,
                payload_json TEXT NOT NULL,
                previous_event_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );

            CREATE TRIGGER IF NOT EXISTS audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN SELECT RAISE(ABORT, 'audit_events_append_only'); END;

            CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN SELECT RAISE(ABORT, 'audit_events_append_only'); END;
            """)

    @staticmethod
    def _event_hash(previous_hash: str, record: dict[str, Any]) -> str:
        if len(previous_hash) != 64:
            raise StoreError("audit:previous_hash")
        return sha256_hex_bytes(bytes.fromhex(previous_hash) + canonical_json(record).encode("utf-8"))

    def _append_audit_tx(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: str,
        timestamp_ms: int,
        event_type: str,
        action_id: str | None,
        permit_id: str | None,
        payload: dict[str, Any],
    ) -> str:
        row = conn.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = row["event_hash"] if row else ZERO_HASH
        payload_json = canonical_json(payload)
        record = {
            "event_id": event_id,
            "timestamp_ms": timestamp_ms,
            "event_type": event_type,
            "action_id": action_id,
            "permit_id": permit_id,
            "payload": json.loads(payload_json),
        }
        event_hash = self._event_hash(previous_hash, record)
        conn.execute(
            """INSERT INTO audit_events(event_id,timestamp_ms,event_type,action_id,permit_id,payload_json,previous_event_hash,event_hash)
               VALUES(?,?,?,?,?,?,?,?)""",
            (event_id, timestamp_ms, event_type, action_id, permit_id, payload_json, previous_hash, event_hash),
        )
        return event_hash

    def append_audit(self, **kwargs: Any) -> str:
        with self._tx() as conn:
            return self._append_audit_tx(conn, **kwargs)

    def verify_audit_chain(self) -> bool:
        conn = self._connect()
        try:
            previous = ZERO_HASH
            for row in conn.execute("SELECT * FROM audit_events ORDER BY seq"):
                record = {
                    "event_id": row["event_id"],
                    "timestamp_ms": row["timestamp_ms"],
                    "event_type": row["event_type"],
                    "action_id": row["action_id"],
                    "permit_id": row["permit_id"],
                    "payload": json.loads(row["payload_json"]),
                }
                if row["previous_event_hash"] != previous:
                    return False
                expected = self._event_hash(previous, record)
                if row["event_hash"] != expected:
                    return False
                previous = row["event_hash"]
            return True
        finally:
            conn.close()

    def register_signer(self, signer_id: str, public_address: str, environment: str, now_ms: int) -> None:
        if environment not in {"TESTNET", "ISOLATED_LIVE"}:
            raise StoreError("signer:environment")
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO signers(signer_id,public_address,environment,enabled,created_at_ms) VALUES(?,?,?,?,?)",
                (signer_id, public_address, environment, 1, now_ms),
            )
            conn.execute("INSERT INTO nonce_state(signer_id,last_nonce) VALUES(?,0)", (signer_id,))
            self._append_audit_tx(
                conn,
                event_id=f"signer-register:{signer_id}:{now_ms}",
                timestamp_ms=now_ms,
                event_type="SIGNER_REGISTERED",
                action_id=None,
                permit_id=None,
                payload={"signer_id": signer_id, "public_address": public_address, "environment": environment},
            )

    def revoke_signer(self, signer_id: str, now_ms: int) -> None:
        with self._tx() as conn:
            cur = conn.execute("UPDATE signers SET enabled=0, revoked_at_ms=? WHERE signer_id=? AND enabled=1", (now_ms, signer_id))
            if cur.rowcount != 1:
                raise StoreError("signer:not_enabled")
            self._append_audit_tx(
                conn,
                event_id=f"signer-revoke:{signer_id}:{now_ms}",
                timestamp_ms=now_ms,
                event_type="SIGNER_REVOKED",
                action_id=None,
                permit_id=None,
                payload={"signer_id": signer_id},
            )

    def signer(self, signer_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM signers WHERE signer_id=?", (signer_id,)).fetchone()
            if row is None:
                raise StoreError("signer:unknown")
            return dict(row)
        finally:
            conn.close()

    def set_execution_state(self, state: str, kill_switch: bool, now_ms: int, event_id: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE system_state SET execution_state=?, kill_switch=?, updated_at_ms=? WHERE id=1",
                (state, int(kill_switch), now_ms),
            )
            self._append_audit_tx(
                conn,
                event_id=event_id,
                timestamp_ms=now_ms,
                event_type="SYSTEM_STATE_CHANGED",
                action_id=None,
                permit_id=None,
                payload={"execution_state": state, "kill_switch": bool(kill_switch)},
            )

    def system_state(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM system_state WHERE id=1").fetchone()
            return dict(row)
        finally:
            conn.close()

    def register_owned_order(self, order_ref: str, instrument: str, cloid: str, terminal: bool, now_ms: int) -> None:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO owned_orders(order_ref,instrument,cloid,terminal,updated_at_ms)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(order_ref) DO UPDATE SET
                     instrument=excluded.instrument, cloid=excluded.cloid,
                     terminal=excluded.terminal, updated_at_ms=excluded.updated_at_ms""",
                (order_ref, instrument, cloid, int(terminal), now_ms),
            )

    def owned_orders(self) -> dict[str, dict[str, Any]]:
        conn = self._connect()
        try:
            return {row["order_ref"]: dict(row) for row in conn.execute("SELECT * FROM owned_orders")}
        finally:
            conn.close()

    @staticmethod
    def _next_nonce_tx(conn: sqlite3.Connection, signer_id: str, now_ms: int) -> int:
        signer = conn.execute("SELECT enabled FROM signers WHERE signer_id=?", (signer_id,)).fetchone()
        if signer is None or signer["enabled"] != 1:
            raise StoreError("signer:disabled_or_unknown")
        row = conn.execute("SELECT last_nonce FROM nonce_state WHERE signer_id=?", (signer_id,)).fetchone()
        if row is None:
            raise StoreError("nonce:missing_state")
        nonce = max(int(now_ms), int(row["last_nonce"]) + 1)
        conn.execute("UPDATE nonce_state SET last_nonce=? WHERE signer_id=?", (nonce, signer_id))
        return nonce

    def create_permit_bundle(
        self,
        *,
        permit_base: dict[str, Any],
        action_id: str,
        action: dict[str, Any],
        risk_increasing: bool,
        expected_quantity: str,
        now_ms: int,
        audit_event_id: str,
    ) -> dict[str, Any]:
        with self._tx() as conn:
            if conn.execute("SELECT 1 FROM permits WHERE permit_id=?", (permit_base["permit_id"],)).fetchone():
                raise StoreError("permit:duplicate")
            local_signer_id = permit_base["signer_id"]
            nonce = self._next_nonce_tx(conn, local_signer_id, now_ms)
            permit = dict(permit_base)
            permit.pop("signer_id", None)
            permit["nonce"] = nonce
            permit_json = canonical_json(permit)
            conn.execute(
                """INSERT INTO permits(
                    permit_id,action_id,signer_id,account_address,action_type,instrument,decision_mode,
                    intent_sha256,compiled_action_sha256,strategy_version_hash,model_version_hash,
                    policy_version_hash,data_snapshot_hash,risk_snapshot_hash,nonce,issued_at_ms,
                    expires_at_ms,cloid,target_cloid,state,permit_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    permit["permit_id"], action_id, local_signer_id, permit["account_address"],
                    permit["action"], permit["instrument"], permit["decision_mode"], permit["intent_sha256"],
                    permit["compiled_action_sha256"], permit["strategy_version_hash"], permit.get("model_version_hash"),
                    permit["policy_version_hash"], permit["data_snapshot_hash"], permit["risk_snapshot_hash"],
                    nonce, permit["issued_at_ms"], permit["expires_at_ms"], permit.get("cloid"),
                    permit.get("target_cloid"), "ISSUED", permit_json,
                ),
            )
            qty = _decimal(expected_quantity, "action:expected_quantity")
            conn.execute(
                """INSERT INTO actions(action_id,permit_id,action_type,instrument,risk_increasing,expected_quantity,filled_quantity,state,action_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    action_id, permit["permit_id"], permit["action"], permit["instrument"], int(risk_increasing),
                    format(qty, "f"), "0", "PERMIT_ISSUED", canonical_json(action),
                ),
            )
            self._append_audit_tx(
                conn,
                event_id=audit_event_id,
                timestamp_ms=now_ms,
                event_type="PERMIT_ISSUED",
                action_id=action_id,
                permit_id=permit["permit_id"],
                payload={"permit_sha256": sha256_hex_bytes(permit_json.encode()), "nonce": nonce, "action_sha256": permit["compiled_action_sha256"]},
            )
            return permit

    def permit(self, permit_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM permits WHERE permit_id=?", (permit_id,)).fetchone()
            if row is None:
                raise StoreError("permit:unknown")
            result = dict(row)
            result["permit"] = json.loads(row["permit_json"])
            return result
        finally:
            conn.close()

    def consume_permit(
        self,
        *,
        permit_id: str,
        signer_id: str,
        action_sha256: str,
        current_policy_hash: str,
        now_ms: int,
        audit_event_id: str,
    ) -> dict[str, Any]:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM permits WHERE permit_id=?", (permit_id,)).fetchone()
            if row is None:
                raise StoreError("permit:unknown")
            if row["state"] != "ISSUED":
                raise StoreError(f"permit:not_issuable:{row['state']}")
            if now_ms >= row["expires_at_ms"]:
                conn.execute("UPDATE permits SET state='EXPIRED' WHERE permit_id=?", (permit_id,))
                self._append_audit_tx(
                    conn, event_id=audit_event_id, timestamp_ms=now_ms, event_type="PERMIT_EXPIRED",
                    action_id=row["action_id"], permit_id=permit_id, payload={}
                )
                raise StoreError("permit:expired")
            signer = conn.execute("SELECT * FROM signers WHERE signer_id=?", (signer_id,)).fetchone()
            if signer is None or signer["enabled"] != 1:
                raise StoreError("signer:disabled_or_unknown")
            state = conn.execute("SELECT * FROM system_state WHERE id=1").fetchone()
            if state["execution_state"] not in {"SIGNED_TEST_ONLY", "ACTIVE_BOUNDED"} or state["kill_switch"] != 0:
                raise StoreError("system:not_signable")
            if row["signer_id"] != signer_id:
                raise StoreError("permit:wrong_signer")
            if row["compiled_action_sha256"] != action_sha256:
                raise StoreError("permit:action_hash_mismatch")
            if row["policy_version_hash"] != current_policy_hash:
                raise StoreError("permit:policy_hash_mismatch")
            cur = conn.execute("UPDATE permits SET state='CONSUMED' WHERE permit_id=? AND state='ISSUED'", (permit_id,))
            if cur.rowcount != 1:
                raise StoreError("permit:consume_race")
            conn.execute("UPDATE actions SET state='PERMIT_CONSUMED' WHERE action_id=?", (row["action_id"],))
            self._append_audit_tx(
                conn,
                event_id=audit_event_id,
                timestamp_ms=now_ms,
                event_type="PERMIT_CONSUMED",
                action_id=row["action_id"],
                permit_id=permit_id,
                payload={"signer_id": signer_id, "action_sha256": action_sha256},
            )
            return json.loads(row["permit_json"])

    def transition_action(self, action_id: str, expected_state: str, target_state: str, now_ms: int, event_id: str, payload: dict[str, Any] | None = None) -> None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None:
                raise StoreError("action:unknown")
            if row["state"] != expected_state:
                raise StoreError(f"action:state:{row['state']}!=expected:{expected_state}")
            cur = conn.execute("UPDATE actions SET state=? WHERE action_id=? AND state=?", (target_state, action_id, expected_state))
            if cur.rowcount != 1:
                raise StoreError("action:transition_race")
            self._append_audit_tx(
                conn, event_id=event_id, timestamp_ms=now_ms, event_type=target_state,
                action_id=action_id, permit_id=row["permit_id"], payload=payload or {}
            )

    def record_fill(self, action_id: str, quantity: str, now_ms: int, event_id: str) -> str:
        qty = _decimal(quantity, "fill:quantity")
        if qty <= 0:
            raise StoreError("fill:nonpositive")
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None:
                raise StoreError("action:unknown")
            if row["state"] not in {"ACKNOWLEDGED", "PARTIALLY_FILLED", "RECONCILING"}:
                raise StoreError(f"fill:invalid_state:{row['state']}")
            expected = _decimal(row["expected_quantity"], "fill:expected")
            filled = _decimal(row["filled_quantity"], "fill:filled")
            total = filled + qty
            if total > expected:
                raise StoreError("fill:exceeds_expected")
            state = "FILLED" if total == expected else "PARTIALLY_FILLED"
            conn.execute("UPDATE actions SET filled_quantity=?, state=? WHERE action_id=?", (format(total, "f"), state, action_id))
            self._append_audit_tx(
                conn, event_id=event_id, timestamp_ms=now_ms, event_type=state,
                action_id=action_id, permit_id=row["permit_id"], payload={"fill_quantity": format(qty, "f"), "filled_total": format(total, "f")}
            )
            return state

    def action(self, action_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None:
                raise StoreError("action:unknown")
            result = dict(row)
            result["action"] = json.loads(row["action_json"])
            return result
        finally:
            conn.close()

    def unresolved_risk_increasing_count(self) -> int:
        terminal = ("FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED_NO_ACTION", "BLOCKED")
        placeholders = ",".join("?" for _ in terminal)
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM actions WHERE risk_increasing=1 AND state NOT IN ({placeholders})",
                terminal,
            ).fetchone()
            return int(row["n"])
        finally:
            conn.close()
