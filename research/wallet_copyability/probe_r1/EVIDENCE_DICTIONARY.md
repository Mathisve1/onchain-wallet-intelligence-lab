# Evidence Dictionary — Hyperliquid Public Probe R1

## Run-level fields

| Field | Meaning | Explicit non-meaning |
|---|---|---|
| `schema_version` | exact output schema revision | venue API version |
| `study_id` | parent research study | validated strategy |
| `probe_id` | immutable technical-probe identity | experiment result ID |
| `contract_sha256` | SHA-256 of exact frozen probe contract bytes | proof that documentation is unchanged |
| `collector_bundle_sha256` | length-delimited SHA-256 over collector/validator source files | proof that GitHub runner executed honestly |
| `collected_at_utc` | first registered request start | server-side event timestamp |
| `completed_at_utc` | output completion time | archive completeness cutoff |
| `scope` | closed technical evidence class | authorization to reuse data analytically |
| `terminal_status` | derived route-level result | alpha, copyability or profitability verdict |
| `archive_access_status` | derived S3 route/list-access class | archive inventory or gap audit |
| `registered_probe_count` | contract probe count | number of available venue endpoints |
| `observation_count` | output observation count | number of successful responses |
| `pass_count` / `fail_count` | response-class matches/mismatches | economically good/bad signals |
| `total_request_attempts` | all initial attempts plus retries | venue-wide request volume |
| `total_declared_request_weight` | conservative frozen API-weight accounting | actual venue throttling charge |
| `security_assertions` | closed set of forbidden-capability flags, all required false | proof of venue/account security |
| `market_data_ingested` | always false in R1 | raw bytes were never processed in memory |
| `empirical_result` | always null in R1 | absence of a technical result |
| `authorizations` | exact project authorization booleans, all false | venue permissions |

## Observation fields

| Field | Meaning |
|---|---|
| `probe_id` | exact ordered contract request identity |
| `core` | whether failure forces `PUBLIC_PROBE_FAIL` |
| `method` | `POST` or `GET` |
| `request_origin` | scheme and authority only |
| `request_path` | path without query values |
| `request_sha256` | hash of canonical POST payload or path-plus-query |
| `declared_weight` | preregistered conservative API weight |
| `attempts` | bounded request attempts for that probe |
| `started_at_utc` / `completed_at_utc` | client-side request window |
| `http_status` | integer status or null after transport failure |
| `elapsed_ms` | client-observed duration of final attempt |
| `transport_error_class` | exception class or null |
| `transport_error_message` | maximum 300-character non-secret message or null |
| `expected_shape` | contract response family |
| `status` | `PASS` only when registered class matches |
| `body_length` | byte length of bounded response body |
| `body_sha256` | SHA-256 of exact response body |
| `content_type` | server-provided header or null |
| `response_class` | `JSON`, `S3_LISTING`, `S3_ERROR_RESPONSE` or `UNSUPPORTED` |
| `json_status` | `VALID_JSON`, `INVALID_JSON` or `NOT_APPLICABLE` |
| `top_level_type` | object, array, null, xml, bytes or scalar class |
| `top_level_keys` | sorted unique keys of root object or first object element |
| `element_count` | root object/array count; null when not applicable |
| `sample_item_types` | sorted unique Python type names from at most first 100 array elements |

## Status semantics

### `PUBLIC_PROBE_PASS`

All 17 response classes matched. This says nothing about archive completeness or wallet economics.

### `PUBLIC_PROBE_PARTIAL`

Every core route matched, but at least one non-core account/relationship route did not. The study remains blocked until repair or an explicit separately reviewed scope decision.

### `PUBLIC_PROBE_FAIL`

At least one core route failed, coverage/order broke, a capacity or integrity gate failed, or forbidden capability appeared.

### `LISTINGS_AVAILABLE`

All three archive routes returned actual S3 list responses. This still does not prove complete object coverage.

### `ROUTES_CONFIRMED_ACCESS_RESTRICTED`

All archive routes produced recognized S3 behavior but at least one returned a valid S3 error response. Likely follow-up topics include requester-pays, access policy or exact request construction. No inventory is open.

### `ARCHIVE_ROUTE_FAILURE`

At least one archive route did not produce a recognized S3 listing/error class.
