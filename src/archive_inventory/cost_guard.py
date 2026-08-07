from __future__ import annotations

from dataclasses import dataclass, field

from .contract import load_contract, load_dataset_register


class GuardViolation(RuntimeError):
    pass


@dataclass
class InventoryGuard:
    started_monotonic: float
    total_requests: int = 0
    total_entries: int = 0
    total_response_bytes: int = 0
    pages_by_family: dict[str, int] = field(default_factory=dict)
    attempts_by_family: dict[str, int] = field(default_factory=dict)
    seen_tokens_by_family: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.contract = load_contract()
        self.families = {row["family"] for row in load_dataset_register()["datasets"]}

    def before_request(self, family: str, *, now_monotonic: float, retry_index: int) -> None:
        if family not in self.families:
            raise GuardViolation("unregistered dataset family")
        limits = self.contract["proposed_canary"]
        if retry_index < 0 or retry_index > limits["max_retries_per_request"]:
            raise GuardViolation("retry cap exceeded")
        if self.total_requests >= limits["max_total_list_requests"]:
            raise GuardViolation("total LIST request cap reached")
        if self.pages_by_family.get(family, 0) >= limits["max_pages_per_family"]:
            raise GuardViolation("family page cap reached")
        if now_monotonic - self.started_monotonic > limits["max_runtime_seconds"]:
            raise GuardViolation("runtime cap reached")
        # Count every attempted LIST before network access. A failure/timeout
        # cannot bypass the request or cost cap.
        self.total_requests += 1
        self.attempts_by_family[family] = self.attempts_by_family.get(family, 0) + 1

    def record_response(self, family: str, *, response_bytes: int, entry_count: int, next_continuation_token: str | None) -> None:
        if family not in self.families:
            raise GuardViolation("unregistered dataset family")
        if response_bytes < 0 or entry_count < 0:
            raise GuardViolation("negative response metric")
        if self.attempts_by_family.get(family, 0) < 1:
            raise GuardViolation("response recorded without prior request attempt")
        if entry_count > self.contract["listing"]["max_keys_per_request"]:
            raise GuardViolation("response entry count exceeds MaxKeys contract")
        limits = self.contract["proposed_canary"]
        new_entries = self.total_entries + entry_count
        new_bytes = self.total_response_bytes + response_bytes
        if new_entries > limits["max_total_entries"]:
            raise GuardViolation("entry cap exceeded")
        if new_bytes > limits["max_total_response_bytes"]:
            raise GuardViolation("response byte cap exceeded")
        pages = self.pages_by_family.get(family, 0) + 1
        if pages > limits["max_pages_per_family"]:
            raise GuardViolation("family page cap exceeded")
        if next_continuation_token is not None:
            if not isinstance(next_continuation_token, str) or not next_continuation_token:
                raise GuardViolation("invalid continuation token")
            seen = self.seen_tokens_by_family.setdefault(family, set())
            if next_continuation_token in seen:
                raise GuardViolation("repeated continuation token")
            seen.add(next_continuation_token)
        self.total_entries = new_entries
        self.total_response_bytes = new_bytes
        self.pages_by_family[family] = pages


def estimate_request_cost_usd(list_request_count: int, list_rate_usd_per_1000: float) -> float:
    if list_request_count < 0 or list_rate_usd_per_1000 < 0:
        raise ValueError("cost inputs must be nonnegative")
    return (list_request_count / 1000.0) * list_rate_usd_per_1000


def estimate_transfer_cost_usd(response_bytes: int, transfer_rate_usd_per_gb: float) -> float:
    if response_bytes < 0 or transfer_rate_usd_per_gb < 0:
        raise ValueError("cost inputs must be nonnegative")
    return (response_bytes / 1_000_000_000.0) * transfer_rate_usd_per_gb
