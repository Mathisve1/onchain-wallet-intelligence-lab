from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import load_contract, load_dataset_register


class ListingPlanError(ValueError):
    pass


@dataclass(frozen=True)
class ListRequestSpec:
    operation: str
    dataset_family: str
    bucket: str
    prefix: str
    delimiter: str | None
    max_keys: int
    request_payer: str
    fetch_owner: bool

    def as_sdk_kwargs(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "Bucket": self.bucket,
            "Prefix": self.prefix,
            "MaxKeys": self.max_keys,
            "RequestPayer": "requester",
            "FetchOwner": False,
        }
        if self.delimiter is not None:
            result["Delimiter"] = self.delimiter
        return result


def _dataset_map() -> dict[str, dict[str, Any]]:
    register = load_dataset_register()
    return {row["family"]: row for row in register["datasets"]}


def build_discovery_request(dataset_family: str) -> ListRequestSpec:
    contract = load_contract()
    datasets = _dataset_map()
    if dataset_family not in datasets:
        raise ListingPlanError(f"unregistered dataset family: {dataset_family}")
    row = datasets[dataset_family]
    spec = ListRequestSpec(
        operation="ListObjectsV2",
        dataset_family=dataset_family,
        bucket=row["bucket"],
        prefix=row["prefix"],
        delimiter="/" if contract["listing"]["delimiter_discovery_first"] else None,
        max_keys=contract["listing"]["max_keys_per_request"],
        request_payer=contract["listing"]["request_payer"],
        fetch_owner=contract["listing"]["fetch_owner"],
    )
    validate_request_spec(spec)
    return spec


def build_page_request(dataset_family: str, continuation_token: str, *, delimiter: str | None = None) -> tuple[ListRequestSpec, str]:
    if not isinstance(continuation_token, str) or not continuation_token:
        raise ListingPlanError("continuation token must be opaque nonempty string")
    base = build_discovery_request(dataset_family)
    spec = ListRequestSpec(
        operation=base.operation,
        dataset_family=base.dataset_family,
        bucket=base.bucket,
        prefix=base.prefix,
        delimiter=delimiter,
        max_keys=base.max_keys,
        request_payer=base.request_payer,
        fetch_owner=base.fetch_owner,
    )
    validate_request_spec(spec)
    return spec, continuation_token


def validate_request_spec(spec: ListRequestSpec) -> None:
    datasets = _dataset_map()
    row = datasets.get(spec.dataset_family)
    if row is None:
        raise ListingPlanError("family not registered")
    if spec.operation != "ListObjectsV2":
        raise ListingPlanError("only ListObjectsV2 is allowed")
    if (spec.bucket, spec.prefix) != (row["bucket"], row["prefix"]):
        raise ListingPlanError("bucket/prefix escaped frozen register")
    if spec.request_payer != "requester":
        raise ListingPlanError("Requester Pays acknowledgement missing")
    if spec.fetch_owner is not False:
        raise ListingPlanError("FetchOwner must remain false")
    if not 1 <= spec.max_keys <= 1000:
        raise ListingPlanError("MaxKeys outside S3 ListObjectsV2 bounds")
    if spec.delimiter not in {None, "/"}:
        raise ListingPlanError("unexpected delimiter")
