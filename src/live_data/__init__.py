"""Read-only Hyperliquid live data pipeline.

Observation only: this package reads the public ``/info`` endpoint and the
public websocket. It holds no keys, signs nothing and contains no write path
to the venue. Every trading authorization in :class:`TradingAuthorizations`
defaults to ``False`` and no code here sets one to ``True``.
"""

from .config import (
    DEFAULT_REST_BASE_URL,
    DEFAULT_WS_URL,
    INFO_PATH,
    READ_ONLY_REST_PATHS,
    ConfigError,
    LiveDataConfig,
    TradingAuthorizations,
    normalize_coin,
    normalize_wallet_address,
)
from .hyperliquid_rest import (
    HttpRequest,
    HttpResponse,
    HyperliquidRestClient,
    RestError,
    RestHttpError,
    build_info_body,
    is_retryable,
    request_weight,
)
from .hyperliquid_ws import (
    CHANNEL_BY_SUBSCRIPTION,
    SUBSCRIPTION_TYPES,
    HyperliquidWebSocketClient,
    Subscription,
    WebSocketError,
    build_subscribe_message,
    build_unsubscribe_message,
)
from .ingest import IngestError, IngestOrchestrator
from .results import BackfillResult, WalletBackfillResult, WatchResult
from .models import (
    AssetPosition,
    ClearinghouseState,
    Fill,
    FundingDelta,
    Meta,
    OpenOrder,
    PayloadError,
    parse_all_mids,
    parse_fills,
    parse_funding,
    parse_open_orders,
)
from .rate_limit import RateLimitError, TokenBucket
from .storage import SCHEMA_VERSION, LiveDataStore, StorageError, WriteResult

__all__ = [
    "AssetPosition",
    "BackfillResult",
    "CHANNEL_BY_SUBSCRIPTION",
    "ClearinghouseState",
    "ConfigError",
    "DEFAULT_REST_BASE_URL",
    "DEFAULT_WS_URL",
    "Fill",
    "FundingDelta",
    "HttpRequest",
    "HttpResponse",
    "HyperliquidRestClient",
    "HyperliquidWebSocketClient",
    "INFO_PATH",
    "IngestError",
    "IngestOrchestrator",
    "LiveDataConfig",
    "LiveDataStore",
    "Meta",
    "OpenOrder",
    "PayloadError",
    "READ_ONLY_REST_PATHS",
    "RateLimitError",
    "RestError",
    "RestHttpError",
    "SCHEMA_VERSION",
    "SUBSCRIPTION_TYPES",
    "StorageError",
    "Subscription",
    "TokenBucket",
    "TradingAuthorizations",
    "WalletBackfillResult",
    "WatchResult",
    "WebSocketError",
    "WriteResult",
    "build_info_body",
    "build_subscribe_message",
    "build_unsubscribe_message",
    "is_retryable",
    "normalize_coin",
    "normalize_wallet_address",
    "parse_all_mids",
    "parse_fills",
    "parse_funding",
    "parse_open_orders",
    "request_weight",
]
