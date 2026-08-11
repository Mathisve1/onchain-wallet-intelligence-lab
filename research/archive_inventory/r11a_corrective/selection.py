from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from .canonical import FrozenObject, NumberToken, strict_json_loads
from .limits import SELECTION_PATH
from .runtime import RuntimeTarget


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
        raise SelectionError(f"expected exactly one field from {names}, observed {observed}")
    return row[observed[0]]


@dataclasses.dataclass(frozen=True, slots=True)
class Selection:
    targets: tuple[RuntimeTarget, ...]
    aggregate_expected_compressed_bytes: int
    complete_utc_day_count: int

    def validate(self) -> None:
        if len(self.targets) != 72:
            raise SelectionError("R11A selection must contain exactly 72 objects")
        if [target.object_ordinal_zero_based for target in self.targets] != list(range(72)):
            raise SelectionError("selection ordinals must be contiguous")
        if len({target.object_key for target in self.targets}) != 72:
            raise SelectionError("selection object keys must be unique")
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
            if re.fullmatch(r'"[0-9a-f]{32}(?:-[0-9]+)?"', target.expected_etag) is None:
                raise SelectionError("selection ETag is malformed")


def load_selection(path: Path = SELECTION_PATH) -> Selection:
    root = _object(strict_json_loads(path.read_bytes()), "selection")
    targets_value = root["exact_targets"]
    if not isinstance(targets_value, tuple):
        raise SelectionError("exact_targets must be an array")
    targets: list[RuntimeTarget] = []
    for ordinal, value in enumerate(targets_value):
        row = _object(value, f"exact_targets[{ordinal}]")
        object_key = _text(_get(row, "key", "object_key"), "object key")
        size = _integer(
            _get(row, "expected_size_bytes", "size", "object_expected_size_bytes"),
            "expected object size",
        )
        etag = _text(_get(row, "expected_etag", "etag", "object_expected_etag"), "expected ETag")
        sha = _text(
            _get(
                row,
                "known_sha256",
                "expected_compressed_sha256",
                "object_expected_compressed_sha256",
            ),
            "expected compressed SHA-256",
        )
        hour = _text(_get(row, "path_hour_utc", "source_path_hour_utc"), "source path hour")
        targets.append(
            RuntimeTarget(
                object_ordinal_zero_based=ordinal,
                object_key=object_key,
                expected_size_bytes=size,
                expected_etag=etag,
                expected_compressed_sha256=sha,
                source_path_hour_utc=hour,
            )
        )
    aggregate = _integer(
        _get(root, "aggregate_expected_compressed_bytes"),
        "aggregate_expected_compressed_bytes",
    )
    days = _integer(_get(root, "complete_utc_day_count"), "complete_utc_day_count")
    selection = Selection(tuple(targets), aggregate, days)
    selection.validate()
    return selection


DEFAULT_SELECTION = load_selection()
