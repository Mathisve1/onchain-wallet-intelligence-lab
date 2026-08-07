from __future__ import annotations

import re
from dataclasses import dataclass

MARKET_DATA = re.compile(r"^market_data/(?P<date>\d{8})/(?P<hour>\d{1,2})/(?P<datatype>[^/]+)/(?P<coin>[^/]+)\.lz4$")
ASSET_CTXS = re.compile(r"^asset_ctxs/(?P<date>\d{8})\.csv\.lz4$")


@dataclass(frozen=True)
class KeyLayout:
    family: str
    matched_documented_layout: bool
    date: str | None = None
    hour: int | None = None
    datatype: str | None = None
    asset: str | None = None


def classify_documented_key(family: str, key: str) -> KeyLayout:
    if family == "market_data":
        match = MARKET_DATA.fullmatch(key)
        if not match:
            return KeyLayout(family, False)
        hour = int(match.group("hour"))
        if not 0 <= hour <= 23:
            return KeyLayout(family, False)
        return KeyLayout(family, True, date=match.group("date"), hour=hour, datatype=match.group("datatype"), asset=match.group("coin"))
    if family == "asset_ctxs":
        match = ASSET_CTXS.fullmatch(key)
        if not match:
            return KeyLayout(family, False)
        return KeyLayout(family, True, date=match.group("date"))
    return KeyLayout(family, False)
