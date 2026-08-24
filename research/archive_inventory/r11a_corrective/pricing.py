from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Final

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .limits import R11ALimits
from .storage_r7 import cleanup_checked_read_bytes

SNAPSHOT_PATH: Final[Path] = Path(__file__).with_name("R11A_PRICING_EUR_SNAPSHOT.json")
_DECIMAL_MICROS: Final[Decimal] = Decimal(1_000_000)
_GIB_BYTES: Final[Decimal] = Decimal(1 << 30)


class PricingError(ValueError):
    pass


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise PricingError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PricingError(f"{label} must be a nonempty string")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, NumberToken):
        try:
            parsed = Decimal(value.token)
        except InvalidOperation as exc:
            raise PricingError(f"{label} is not an exact decimal") from exc
        if not parsed.is_finite() or parsed < 0:
            raise PricingError(f"{label} must be finite and nonnegative")
        return parsed
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise PricingError(f"{label} must be nonnegative")
        return Decimal(value)
    raise PricingError(f"{label} must be an exact JSON number")


@dataclasses.dataclass(frozen=True, slots=True)
class PricingSnapshot:
    status: str
    region: str
    currency: str
    get_request_usd_per_1000: Decimal
    data_transfer_out_usd_per_gib: Decimal
    usd_per_eur: Decimal
    contingency_multiplier: Decimal
    aws_pricing_source_url: str
    aws_pricing_source_sha256: str
    ecb_fx_source_url: str
    ecb_fx_source_sha256: str
    snapshot_sha256: str
    observed_at_utc: str

    @classmethod
    def load(cls, path: Path = SNAPSHOT_PATH) -> "PricingSnapshot":
        root = _object(
            strict_json_loads(
                cleanup_checked_read_bytes(
                    path,
                    label="pricing snapshot",
                )
            ),
            "pricing snapshot",
        )
        values = cls(
            status=_text(root["status"], "status"),
            region=_text(root["region"], "region"),
            currency=_text(root["currency"], "currency"),
            get_request_usd_per_1000=_decimal(
                root["get_request_usd_per_1000"], "get_request_usd_per_1000"
            ),
            data_transfer_out_usd_per_gib=_decimal(
                root["data_transfer_out_usd_per_gib"],
                "data_transfer_out_usd_per_gib",
            ),
            usd_per_eur=_decimal(root["usd_per_eur"], "usd_per_eur"),
            contingency_multiplier=_decimal(
                root["contingency_multiplier"], "contingency_multiplier"
            ),
            aws_pricing_source_url=_text(
                root["aws_pricing_source_url"], "aws_pricing_source_url"
            ),
            aws_pricing_source_sha256=_text(
                root["aws_pricing_source_sha256"], "aws_pricing_source_sha256"
            ),
            ecb_fx_source_url=_text(root["ecb_fx_source_url"], "ecb_fx_source_url"),
            ecb_fx_source_sha256=_text(
                root["ecb_fx_source_sha256"], "ecb_fx_source_sha256"
            ),
            snapshot_sha256=_text(root["snapshot_sha256"], "snapshot_sha256"),
            observed_at_utc=_text(root["observed_at_utc"], "observed_at_utc"),
        )
        values.validate()
        return values

    def validate(self) -> None:
        if self.status != "BOUND_CURRENT_OFFICIAL_SNAPSHOT":
            raise PricingError("pricing and EUR snapshot is not bound for approval")
        if self.region != "ap-northeast-1" or self.currency != "USD":
            raise PricingError("pricing snapshot region or currency drift")
        if self.usd_per_eur <= 0:
            raise PricingError("USD per EUR rate must be positive")
        if self.contingency_multiplier < 1:
            raise PricingError("pricing contingency multiplier may not reduce cost")
        for digest in (
            self.aws_pricing_source_sha256,
            self.ecb_fx_source_sha256,
            self.snapshot_sha256,
        ):
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise PricingError("pricing snapshot SHA-256 must be lowercase hexadecimal")
        if not self.aws_pricing_source_url.startswith("https://"):
            raise PricingError("AWS pricing source must use HTTPS")
        if not self.ecb_fx_source_url.startswith("https://"):
            raise PricingError("ECB FX source must use HTTPS")

    def projected_eur_micros(self, request_count: int, response_bytes: int) -> int:
        if request_count < 0 or response_bytes < 0:
            raise PricingError("projected usage cannot be negative")
        request_usd = Decimal(request_count) * self.get_request_usd_per_1000 / Decimal(1000)
        transfer_usd = Decimal(response_bytes) * self.data_transfer_out_usd_per_gib / _GIB_BYTES
        projected_eur = (request_usd + transfer_usd) / self.usd_per_eur
        projected_eur *= self.contingency_multiplier
        micros = (projected_eur * _DECIMAL_MICROS).to_integral_value(rounding=ROUND_CEILING)
        return int(micros)


@dataclasses.dataclass(slots=True)
class BudgetGuard:
    limits: R11ALimits
    snapshot: PricingSnapshot
    expected_total_response_bytes: int
    authorized_request_count: int = 0
    authorized_response_bytes: int = 0

    def __post_init__(self) -> None:
        self.limits.validate()
        self.snapshot.validate()
        if self.expected_total_response_bytes != self.limits.maximum_total_compressed_bytes:
            raise PricingError("budget guard response-byte envelope drift")
        total_projection = self.snapshot.projected_eur_micros(
            self.limits.maximum_get_object_requests,
            self.expected_total_response_bytes,
        )
        if total_projection > self.limits.maximum_one_time_budget_eur_micros:
            raise PricingError("frozen R11A execution would exceed owner budget")
        if self.limits.maximum_monthly_budget_eur_micros != 0:
            raise PricingError("R11A recurring monthly budget is forbidden")

    def authorize_request(
        self,
        *,
        request_ordinal_zero_based: int,
        expected_response_bytes: int,
    ) -> int:
        if request_ordinal_zero_based != self.authorized_request_count:
            raise PricingError("request budget authorization order drift")
        if self.authorized_request_count >= self.limits.maximum_get_object_requests:
            raise PricingError("request budget count exceeded")
        next_bytes = self.authorized_response_bytes + expected_response_bytes
        if next_bytes > self.expected_total_response_bytes:
            raise PricingError("response-byte budget exceeded")
        next_count = self.authorized_request_count + 1
        projection = self.snapshot.projected_eur_micros(next_count, next_bytes)
        if projection > self.limits.maximum_one_time_budget_eur_micros:
            raise PricingError("next request would exceed one-time EUR budget")
        self.authorized_request_count = next_count
        self.authorized_response_bytes = next_bytes
        return projection
