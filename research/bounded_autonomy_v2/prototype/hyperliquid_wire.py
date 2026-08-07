from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class WireError(ValueError):
    pass


def normalize_wire_decimal(value: str) -> str:
    if not isinstance(value, str) or value.strip() != value or "e" in value.lower() or value.startswith("+"):
        raise WireError("wire:noncanonical_decimal")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise WireError("wire:invalid_decimal") from exc
    if not d.is_finite():
        raise WireError("wire:nonfinite")
    if d.as_tuple().exponent < -8:
        quant = Decimal("0.00000001")
        if d.quantize(quant) != d:
            raise WireError("wire:more_than_8_decimals")
    if d == 0:
        return "0"
    return format(d.normalize(), "f")


def order_wire(
    *,
    asset: int,
    is_buy: bool,
    limit_price: str,
    size: str,
    reduce_only: bool,
    cloid: str,
) -> dict[str, Any]:
    if not isinstance(asset, int) or asset < 0:
        raise WireError("wire:asset")
    if not isinstance(cloid, str) or not cloid.startswith("0x") or len(cloid) != 34:
        raise WireError("wire:cloid")
    return {
        "a": asset,
        "b": bool(is_buy),
        "p": normalize_wire_decimal(limit_price),
        "s": normalize_wire_decimal(size),
        "r": bool(reduce_only),
        "t": {"limit": {"tif": "Ioc"}},
        "c": cloid,
    }


def order_action(wire: dict[str, Any]) -> dict[str, Any]:
    return {"type": "order", "orders": [wire], "grouping": "na"}


def cancel_by_cloid_action(*, asset: int, cloid: str) -> dict[str, Any]:
    if not isinstance(asset, int) or asset < 0:
        raise WireError("wire:asset")
    if not isinstance(cloid, str) or not cloid.startswith("0x") or len(cloid) != 34:
        raise WireError("wire:cloid")
    return {"type": "cancelByCloid", "cancels": [{"asset": asset, "cloid": cloid}]}
