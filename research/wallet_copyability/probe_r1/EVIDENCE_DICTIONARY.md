# Evidence Dictionary — Hyperliquid Public Probe R1

## Run fields

| Field | Meaning | Not evidence of |
|---|---|---|
| `contract_sha256` | exact frozen contract bytes | unchanged external documentation |
| `collector_bundle_sha256` | exact collector/validator bundle bytes | honest hosted-runner execution by itself |
| `terminal_status` | derived route-level result | alpha, copyability or profitability |
| `archive_access_status` | derived S3 route/access class | archive inventory or completeness |
| `published_ip_budget_per_minute` | frozen planning reference | permanent rate-limit guarantee |
| `total_declared_request_weight` | sum of registered weights times attempts | actual charged venue weight |
| `remaining_declared_weight_margin` | planning budget minus declared run weight | spare production capacity |
| `security_assertions` | exact forbidden-capability flags, all false | venue/account security audit |
| `market_data_ingested` | false: no analytical market partition opened | raw bodies were never processed in memory |
| `empirical_result` | null in R1 | absence of a technical result |

## Observation fields

`probe_id`, `core`, `method`, `request_origin`, `request_path`, `request_sha256`, `declared_weight`, `weight_basis`, `attempts`, UTC start/completion, `http_status`, `elapsed_ms`, transport error class/message, `expected_shape`, derived `status`, response byte length/SHA-256/content type/class, JSON status, top-level type/keys/count and bounded sample item types.

No raw account or market values are retained.

## Status meanings

- `PUBLIC_PROBE_PASS`: all 16 route response classes matched.
- `PUBLIC_PROBE_PARTIAL`: all core routes matched; one or more non-core routes did not.
- `PUBLIC_PROBE_FAIL`: core, coverage, capacity, integrity or security failure.
- `LISTINGS_AVAILABLE`: all three S3 routes returned actual list responses; completeness still unproven.
- `ROUTES_CONFIRMED_ACCESS_RESTRICTED`: recognized S3 behavior but at least one route returned a valid error response.
- `ARCHIVE_ROUTE_FAILURE`: at least one archive route did not return a recognized S3 class.
