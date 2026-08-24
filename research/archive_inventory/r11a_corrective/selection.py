from __future__ import annotations

import dataclasses
import hashlib
import re
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .limits import PREREGISTRATION_PATH, ROOT, SELECTION_PATH
from .runtime import RuntimeTarget

R11_RESULT_PATH = (
    ROOT
    / "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
)


class SelectionError(ValueError):
    pass


def _object(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise SelectionError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SelectionError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise SelectionError(f"{label} must be an exact integer")


def _get(row: FrozenObject, *names: str) -> object:
    observed = [name for name in names if name in row]
    if len(observed) != 1:
        raise SelectionError(
            f"expected exactly one field from {names}, observed {observed}"
        )
    return row[observed[0]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class Selection:
    targets: tuple[RuntimeTarget, ...]
    aggregate_expected_compressed_bytes: int
    complete_utc_day_count: int

    def validate(self) -> None:
        if len(self.targets) != 72:
            raise SelectionError("R11A selection must contain exactly 72 objects")
        if [target.object_ordinal_zero_based for target in self.targets] != list(
            range(72)
        ):
            raise SelectionError("selection ordinals must be contiguous")
        if len({target.object_key for target in self.targets}) != 72:
            raise SelectionError("selection object keys must be unique")
        if len({target.expected_compressed_sha256 for target in self.targets}) != 72:
            raise SelectionError("selection compressed SHA-256 values must be unique")
        if sum(target.expected_size_bytes for target in self.targets) != 2_107_738_436:
            raise SelectionError("selection aggregate compressed bytes drift")
        if max(target.expected_size_bytes for target in self.targets) != 76_616_104:
            raise SelectionError("selection maximum object size drift")
        if self.aggregate_expected_compressed_bytes != 2_107_738_436:
            raise SelectionError("declared aggregate compressed bytes drift")
        if self.complete_utc_day_count != 3:
            raise SelectionError("selection must span exactly three complete UTC days")
        expected_hours: list[str] = []
        for day in (28, 29, 30):
            for hour in range(24):
                expected_hours.append(f"2025-07-{day:02d}T{hour:02d}:00:00Z")
        if [target.source_path_hour_utc for target in self.targets] != expected_hours:
            raise SelectionError("selection hours are not the exact frozen 72-hour sequence")
        for target, hour in zip(self.targets, expected_hours):
            day_compact = hour[0:10].replace("-", "")
            numeric_hour = str(int(hour[11:13]))
            expected_key = f"node_fills_by_block/hourly/{day_compact}/{numeric_hour}.lz4"
            if target.object_key != expected_key:
                raise SelectionError("selection object key does not match source path hour")
            if re.fullmatch(
                r'"[0-9a-f]{32}(?:-[0-9]+)?"', target.expected_etag
            ) is None:
                raise SelectionError("selection ETag is malformed")
            if re.fullmatch(
                r"[0-9a-f]{64}", target.expected_compressed_sha256
            ) is None:
                raise SelectionError("selection compressed SHA-256 is malformed")


def load_selection(
    path: Path = SELECTION_PATH,
    prior_result_path: Path = R11_RESULT_PATH,
    preregistration_path: Path = PREREGISTRATION_PATH,
) -> Selection:
    preregistration = _object(
        strict_json_loads(preregistration_path.read_bytes()),
        "corrective preregistration",
    )
    exact_scope = _object(
        preregistration["exact_input_scope"], "exact_input_scope"
    )
    expected_selection_path = "research/archive_inventory/r11/R11_72H_SELECTION.json"
    expected_prior_path = (
        "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
    )
    if exact_scope["selection_path"] != expected_selection_path:
        raise SelectionError("preregistered selection path drift")
    if exact_scope["prior_result_path"] != expected_prior_path:
        raise SelectionError("preregistered prior-result path drift")
    if _sha256(path) != _text(exact_scope["selection_sha256"], "selection SHA-256"):
        raise SelectionError("selection bytes do not match preregistration")
    if _sha256(prior_result_path) != _text(
        exact_scope["prior_result_sha256"], "prior-result SHA-256"
    ):
        raise SelectionError("prior R11 result bytes do not match preregistration")

    root = _object(strict_json_loads(path.read_bytes()), "selection")
    prior_result = _object(
        strict_json_loads(prior_result_path.read_bytes()), "prior R11 result"
    )
    if _integer(prior_result["completed_hour_count"], "completed hour count") != 72:
        raise SelectionError("prior R11 result does not contain 72 completed hours")
    if _integer(prior_result["completed_day_count"], "completed day count") != 3:
        raise SelectionError("prior R11 result does not contain three completed days")
    if _integer(prior_result["failed_request_count"], "failed request count") != 0:
        raise SelectionError("prior R11 result contains failed requests")

    summaries_value = prior_result["per_hour_summaries"]
    if not isinstance(summaries_value, tuple) or len(summaries_value) != 72:
        raise SelectionError("prior R11 per-hour evidence must contain 72 rows")
    evidence_by_key: dict[str, FrozenObject] = {}
    for ordinal, value in enumerate(summaries_value):
        evidence = _object(value, f"per_hour_summaries[{ordinal}]")
        key = _text(evidence["object_key"], "evidence object key")
        if key in evidence_by_key:
            raise SelectionError("duplicate object key in prior R11 evidence")
        evidence_by_key[key] = evidence

    targets_value = root["exact_targets"]
    if not isinstance(targets_value, tuple):
        raise SelectionError("exact_targets must be an array")
    targets: list[RuntimeTarget] = []
    for ordinal, value in enumerate(targets_value):
        row = _object(value, f"exact_targets[{ordinal}]")
        object_key = _text(_get(row, "key", "object_key"), "object key")
        size = _integer(
            _get(
                row,
                "expected_size_bytes",
                "size",
                "object_expected_size_bytes",
            ),
            "expected object size",
        )
        etag = _text(
            _get(row, "expected_etag", "etag", "object_expected_etag"),
            "expected ETag",
        )
        hour = _text(
            _get(row, "path_hour_utc", "source_path_hour_utc"),
            "source path hour",
        )
        evidence = evidence_by_key.get(object_key)
        if evidence is None:
            raise SelectionError("selection object is absent from prior R11 evidence")
        evidence_size = _integer(
            evidence["expected_content_length"], "evidence expected content length"
        )
        evidence_observed_size = _integer(
            evidence["observed_content_length"], "evidence observed content length"
        )
        evidence_etag = _text(evidence["expected_etag"], "evidence ETag")
        evidence_hour = _text(evidence["path_hour_utc"], "evidence path hour")
        evidence_sha = _text(
            evidence["compressed_sha256"], "evidence compressed SHA-256"
        )
        if size != evidence_size or size != evidence_observed_size:
            raise SelectionError("selection and prior-evidence size mismatch")
        if etag != evidence_etag:
            raise SelectionError("selection and prior-evidence ETag mismatch")
        if hour != evidence_hour:
            raise SelectionError("selection and prior-evidence hour mismatch")
        inline_sha_fields = [
            name
            for name in (
                "known_sha256",
                "expected_compressed_sha256",
                "object_expected_compressed_sha256",
            )
            if name in row
        ]
        if len(inline_sha_fields) > 1:
            raise SelectionError("multiple inline compressed SHA-256 fields")
        if inline_sha_fields and _text(
            row[inline_sha_fields[0]], "inline compressed SHA-256"
        ) != evidence_sha:
            raise SelectionError(
                "inline selection SHA-256 conflicts with prior R11 evidence"
            )
        targets.append(
            RuntimeTarget(
                object_ordinal_zero_based=ordinal,
                object_key=object_key,
                expected_size_bytes=size,
                expected_etag=etag,
                expected_compressed_sha256=evidence_sha,
                source_path_hour_utc=hour,
            )
        )

    if {target.object_key for target in targets} != set(evidence_by_key):
        raise SelectionError("selection and prior R11 evidence key sets differ")
    aggregate = _integer(
        _get(root, "aggregate_expected_compressed_bytes"),
        "aggregate_expected_compressed_bytes",
    )
    days = _integer(_get(root, "complete_utc_day_count"), "complete_utc_day_count")
    selection = Selection(tuple(targets), aggregate, days)
    selection.validate()
    return selection


DEFAULT_SELECTION = load_selection()
