from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
CLOID_RE = re.compile(r"^0x[0-9a-f]{32}$")
ORDER_REF_RE = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")

ALLOWED_ACTIONS = {"PLACE_IOC_LIMIT", "REDUCE_ONLY_IOC", "CANCEL_BY_CLOID"}
ALLOWED_INSTRUMENTS = {"BTC", "ETH", "SOL"}
AI_STATUSES = {"NOT_USED", "PASS", "VETO", "TIMEOUT", "ERROR"}
UPWARD_STATES = ["DISABLED", "RESEARCH_ONLY", "SHADOW_ONLY", "SIGNED_TEST_ONLY", "ACTIVE_BOUNDED"]


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    details: tuple[str, ...] = ()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    data = value if isinstance(value, (bytes, bytearray)) else canonical_json_bytes(value)
    return hashlib.sha256(bytes(data)).hexdigest()


def decimal_string(value: Any, label: str, *, allow_zero: bool = False, allow_negative: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise PolicyError(f"{label}:must_be_decimal_string")
    if value.startswith("+") or "e" in value.lower() or value.strip() != value:
        raise PolicyError(f"{label}:noncanonical_decimal")
    try:
        out = Decimal(value)
    except InvalidOperation as exc:
        raise PolicyError(f"{label}:invalid_decimal") from exc
    if not out.is_finite():
        raise PolicyError(f"{label}:nonfinite")
    if allow_negative:
        return out
    if allow_zero:
        if out < 0:
            raise PolicyError(f"{label}:negative")
    elif out <= 0:
        raise PolicyError(f"{label}:nonpositive")
    return out


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise PolicyError(f"{label}:invalid_sha256")
    return value


def validate_risk_envelope(envelope: dict[str, Any], now_ms: int) -> None:
    if envelope.get("schema_version") != "0.1-design":
        raise PolicyError("envelope:schema")
    if envelope.get("venue") != "HYPERLIQUID":
        raise PolicyError("envelope:venue")
    if envelope.get("environment") not in {"TESTNET", "ISOLATED_LIVE"}:
        raise PolicyError("envelope:environment")
    if ADDRESS_RE.fullmatch(str(envelope.get("account_address", ""))) is None:
        raise PolicyError("envelope:account")
    require_sha256(envelope.get("policy_hash"), "envelope:policy_hash")
    if envelope.get("human_governor_signature_required_for_activation") is not True:
        raise PolicyError("envelope:human_activation")
    if not isinstance(envelope.get("effective_from_ms"), int) or not isinstance(envelope.get("expires_at_ms"), int):
        raise PolicyError("envelope:time_type")
    if not (envelope["effective_from_ms"] <= now_ms < envelope["expires_at_ms"]):
        raise PolicyError("envelope:not_active")
    instruments = set(envelope.get("allowed_instruments", []))
    actions = set(envelope.get("allowed_actions", []))
    if not instruments or not instruments <= ALLOWED_INSTRUMENTS:
        raise PolicyError("envelope:instrument_allowlist")
    if not actions or not actions <= ALLOWED_ACTIONS:
        raise PolicyError("envelope:action_allowlist")
    for key in (
        "max_single_trade_notional_usd",
        "max_gross_exposure_usd",
        "max_net_exposure_usd",
        "max_daily_realized_loss_usd",
        "max_daily_total_loss_usd",
        "max_strategy_drawdown_usd",
    ):
        decimal_string(envelope.get(key), f"envelope:{key}", allow_zero=True)
    if envelope.get("max_unreconciled_actions") != 0:
        raise PolicyError("envelope:unreconciled_must_be_zero")
    if not isinstance(envelope.get("max_slippage_bps"), int) or not (0 <= envelope["max_slippage_bps"] <= 10000):
        raise PolicyError("envelope:slippage")
    if not isinstance(envelope.get("max_signal_age_ms"), int) or envelope["max_signal_age_ms"] <= 0:
        raise PolicyError("envelope:signal_age")
    if not isinstance(envelope.get("max_quote_age_ms"), int) or envelope["max_quote_age_ms"] <= 0:
        raise PolicyError("envelope:quote_age")
    if not isinstance(envelope.get("max_open_positions"), int) or envelope["max_open_positions"] < 0:
        raise PolicyError("envelope:open_positions")
    if not isinstance(envelope.get("min_cancel_action_reserve"), int) or envelope["min_cancel_action_reserve"] <= 0:
        raise PolicyError("envelope:cancel_reserve")


def _validate_common_intent(
    intent: dict[str, Any],
    envelope: dict[str, Any],
    *,
    now_ms: int,
    current_policy_hash: str,
) -> Decision | None:
    if intent.get("schema_version") != "0.2-design":
        return Decision(False, "BLOCK_INTENT_SCHEMA")
    action = intent.get("action")
    instrument = intent.get("instrument")
    if action not in ALLOWED_ACTIONS or action not in set(envelope["allowed_actions"]):
        return Decision(False, "BLOCK_ACTION")
    if instrument not in ALLOWED_INSTRUMENTS or instrument not in set(envelope["allowed_instruments"]):
        return Decision(False, "BLOCK_INSTRUMENT")
    if intent.get("expires_at_ms", 0) <= now_ms:
        return Decision(False, "BLOCK_EXPIRED")
    decision_ts = intent.get("decision_timestamp_ms")
    if not isinstance(decision_ts, int) or decision_ts > now_ms:
        return Decision(False, "BLOCK_DECISION_TIME")
    if now_ms - decision_ts > envelope["max_signal_age_ms"]:
        return Decision(False, "BLOCK_SIGNAL_STALE")
    policy_hash = require_sha256(intent.get("policy_version_hash"), "intent:policy_hash")
    if policy_hash != current_policy_hash or current_policy_hash != envelope["policy_hash"]:
        return Decision(False, "BLOCK_POLICY_HASH")
    for key in ("strategy_version_hash", "model_version_hash", "data_snapshot_hash", "risk_snapshot_hash"):
        require_sha256(intent.get(key), f"intent:{key}")
    ai = intent.get("ai_assessment")
    if not isinstance(ai, dict) or ai.get("status") not in AI_STATUSES:
        return Decision(False, "BLOCK_AI_ASSESSMENT")
    if ai.get("veto") is True or ai.get("status") == "VETO":
        return Decision(False, "BLOCK_AI_VETO")
    mode = envelope.get("ai_critic_mode")
    if mode == "VETO_ONLY_REQUIRED" and ai.get("status") != "PASS":
        return Decision(False, "SKIP_AI_REQUIRED")
    return None


def _validate_owned_cancel(intent: dict[str, Any], risk_state: dict[str, Any]) -> Decision:
    ref = intent.get("target_strategy_order_id")
    if not isinstance(ref, str) or ORDER_REF_RE.fullmatch(ref) is None:
        return Decision(False, "BLOCK_CANCEL_TARGET")
    order = risk_state.get("strategy_orders", {}).get(ref)
    if not isinstance(order, dict):
        return Decision(False, "BLOCK_CANCEL_NOT_OWNED")
    if order.get("instrument") != intent.get("instrument"):
        return Decision(False, "BLOCK_CANCEL_INSTRUMENT_MISMATCH")
    if order.get("terminal") is True:
        return Decision(False, "BLOCK_CANCEL_ALREADY_TERMINAL")
    if CLOID_RE.fullmatch(str(order.get("cloid", ""))) is None:
        return Decision(False, "BLOCK_CANCEL_CLOID_INVALID")
    return Decision(True, "ALLOW_CANCEL")


def _validate_reduce_only(
    intent: dict[str, Any],
    risk_state: dict[str, Any],
    *,
    quote_timestamp_ms: int,
    now_ms: int,
    envelope: dict[str, Any],
) -> Decision | None:
    if intent.get("side") not in {"BUY", "SELL"}:
        return Decision(False, "BLOCK_SIDE")
    if intent.get("reduce_only") is not True:
        return Decision(False, "BLOCK_REDUCE_ONLY_MISMATCH")
    if quote_timestamp_ms > now_ms or now_ms - quote_timestamp_ms > envelope["max_quote_age_ms"]:
        return Decision(False, "BLOCK_QUOTE_STALE")
    slippage = intent.get("max_slippage_bps")
    if not isinstance(slippage, int) or slippage < 0 or slippage > envelope["max_slippage_bps"]:
        return Decision(False, "BLOCK_SLIPPAGE")
    qty = decimal_string(intent.get("requested_quantity"), "intent:quantity")
    decimal_string(intent.get("limit_price"), "intent:price")
    pos = decimal_string(
        str(risk_state.get("position_quantity", {}).get(intent["instrument"], "0")),
        "state:position",
        allow_negative=True,
    )
    if pos == 0:
        return Decision(False, "BLOCK_NO_POSITION_TO_REDUCE")
    expected_side = "SELL" if pos > 0 else "BUY"
    if intent["side"] != expected_side:
        return Decision(False, "BLOCK_REDUCE_WRONG_SIDE")
    if qty > abs(pos):
        return Decision(False, "BLOCK_REDUCE_EXCEEDS_POSITION")
    return None


def evaluate_intent(
    intent: dict[str, Any],
    envelope: dict[str, Any],
    risk_state: dict[str, Any],
    *,
    now_ms: int,
    quote_timestamp_ms: int,
    current_policy_hash: str,
) -> Decision:
    try:
        validate_risk_envelope(envelope, now_ms)
        if risk_state.get("execution_state") != "ACTIVE_BOUNDED":
            return Decision(False, "BLOCK_EXECUTION_STATE")
        if risk_state.get("kill_switch") is not False:
            return Decision(False, "BLOCK_KILL_SWITCH")
        if risk_state.get("unreconciled_actions") != 0:
            return Decision(False, "BLOCK_UNRECONCILED")
        if risk_state.get("cancel_action_reserve", 0) < envelope["min_cancel_action_reserve"]:
            return Decision(False, "BLOCK_CANCEL_RESERVE")
        common = _validate_common_intent(
            intent, envelope, now_ms=now_ms, current_policy_hash=current_policy_hash
        )
        if common is not None:
            return common
        action = intent["action"]
        if action == "CANCEL_BY_CLOID":
            return _validate_owned_cancel(intent, risk_state)

        if action == "REDUCE_ONLY_IOC":
            reduction = _validate_reduce_only(
                intent,
                risk_state,
                quote_timestamp_ms=quote_timestamp_ms,
                now_ms=now_ms,
                envelope=envelope,
            )
            if reduction is not None:
                return reduction
            return Decision(True, "ALLOW_REDUCE_ONLY")

        # From here on only new risk / PLACE_IOC_LIMIT remains.
        if intent.get("side") not in {"BUY", "SELL"}:
            return Decision(False, "BLOCK_SIDE")
        if intent.get("reduce_only") is not False:
            return Decision(False, "BLOCK_REDUCE_ONLY_MISMATCH")
        if quote_timestamp_ms > now_ms or now_ms - quote_timestamp_ms > envelope["max_quote_age_ms"]:
            return Decision(False, "BLOCK_QUOTE_STALE")
        slippage = intent.get("max_slippage_bps")
        if not isinstance(slippage, int) or slippage < 0 or slippage > envelope["max_slippage_bps"]:
            return Decision(False, "BLOCK_SLIPPAGE")

        qty = decimal_string(intent.get("requested_quantity"), "intent:quantity")
        px = decimal_string(intent.get("limit_price"), "intent:price")
        notional = qty * px
        if notional > decimal_string(envelope["max_single_trade_notional_usd"], "envelope:max_trade", allow_zero=True):
            return Decision(False, "BLOCK_TRADE_NOTIONAL")

        gross = decimal_string(str(risk_state.get("gross_exposure_usd")), "state:gross", allow_zero=True)
        net_abs = abs(decimal_string(str(risk_state.get("net_exposure_usd")), "state:net", allow_negative=True))
        if gross + notional > decimal_string(envelope["max_gross_exposure_usd"], "envelope:max_gross", allow_zero=True):
            return Decision(False, "BLOCK_GROSS_EXPOSURE")
        if net_abs + notional > decimal_string(envelope["max_net_exposure_usd"], "envelope:max_net", allow_zero=True):
            return Decision(False, "BLOCK_NET_EXPOSURE")

        instrument = intent["instrument"]
        inst_exp = decimal_string(
            str(risk_state.get("instrument_exposure_usd", {}).get(instrument, "0")),
            "state:instrument",
            allow_zero=True,
        )
        inst_cap = decimal_string(
            envelope.get("max_instrument_exposure_usd", {}).get(instrument, "0"),
            "envelope:instrument_cap",
            allow_zero=True,
        )
        if inst_exp + notional > inst_cap:
            return Decision(False, "BLOCK_INSTRUMENT_EXPOSURE")
        if risk_state.get("open_positions", 0) >= envelope["max_open_positions"] and inst_exp == 0:
            return Decision(False, "BLOCK_OPEN_POSITIONS")

        for state_key, cap_key, code in (
            ("daily_realized_loss_usd", "max_daily_realized_loss_usd", "BLOCK_DAILY_REALIZED_LOSS"),
            ("daily_total_loss_usd", "max_daily_total_loss_usd", "BLOCK_DAILY_TOTAL_LOSS"),
            ("strategy_drawdown_usd", "max_strategy_drawdown_usd", "BLOCK_DRAWDOWN"),
        ):
            loss = decimal_string(str(risk_state.get(state_key)), f"state:{state_key}", allow_zero=True)
            cap = decimal_string(envelope[cap_key], f"envelope:{cap_key}", allow_zero=True)
            if loss >= cap:
                return Decision(False, code)
        return Decision(True, "ALLOW")
    except PolicyError as exc:
        return Decision(False, "BLOCK_INVALID_INPUT", (str(exc),))


def derive_cloid(strategy_id: str, permit_id: str, sequence: int, environment: str) -> str:
    if not strategy_id or not permit_id or sequence < 0 or environment not in {"TESTNET", "ISOLATED_LIVE"}:
        raise PolicyError("cloid:invalid_input")
    raw = f"{strategy_id}\0{permit_id}\0{sequence}\0{environment}".encode()
    return "0x" + hashlib.sha256(raw).hexdigest()[:32]


def compile_abstract_action(
    intent: dict[str, Any],
    *,
    new_order_cloid: str | None = None,
    owned_orders: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    action = intent.get("action")
    if action == "CANCEL_BY_CLOID":
        ref = intent.get("target_strategy_order_id")
        order = (owned_orders or {}).get(ref)
        if not isinstance(order, dict):
            raise PolicyError("compile:cancel_not_owned")
        target_cloid = str(order.get("cloid", ""))
        if CLOID_RE.fullmatch(target_cloid) is None:
            raise PolicyError("compile:cancel_cloid")
        if order.get("instrument") != intent.get("instrument"):
            raise PolicyError("compile:cancel_instrument")
        return {
            "action_type": "cancelByCloid",
            "coin": intent["instrument"],
            "target_cloid": target_cloid,
        }

    if action not in {"PLACE_IOC_LIMIT", "REDUCE_ONLY_IOC"}:
        raise PolicyError("compile:unsupported_action")
    if new_order_cloid is None or CLOID_RE.fullmatch(new_order_cloid) is None:
        raise PolicyError("compile:new_order_cloid")
    return {
        "action_type": "order",
        "coin": intent["instrument"],
        "is_buy": intent["side"] == "BUY",
        "size": intent["requested_quantity"],
        "limit_price": intent["limit_price"],
        "order_type": {"limit": {"tif": "Ioc"}},
        "reduce_only": bool(intent["reduce_only"]),
        "cloid": new_order_cloid,
    }


class PermitRegistry:
    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(self, permit_id: str) -> None:
        if permit_id in self._consumed:
            raise PolicyError("permit:replay")
        self._consumed.add(permit_id)

    def is_consumed(self, permit_id: str) -> bool:
        return permit_id in self._consumed


class ExecutionStateMachine:
    def __init__(self, state: str = "RESEARCH_ONLY") -> None:
        if state not in UPWARD_STATES and state not in {"PAUSED", "LOCKED_REQUIRES_ROTATION"}:
            raise PolicyError("state:invalid")
        self.state = state

    def restrict(self, target: str) -> None:
        if target not in {"PAUSED", "LOCKED_REQUIRES_ROTATION", "DISABLED"}:
            raise PolicyError("state:invalid_restriction")
        self.state = target

    def human_promote(self, target: str) -> None:
        if target not in UPWARD_STATES:
            raise PolicyError("state:invalid_promotion")
        if self.state not in UPWARD_STATES:
            raise PolicyError("state:recovery_required")
        if UPWARD_STATES.index(target) != UPWARD_STATES.index(self.state) + 1:
            raise PolicyError("state:nonsequential_promotion")
        self.state = target

    def automated_promote(self, target: str) -> None:
        raise PolicyError("state:automated_upward_transition_forbidden")
