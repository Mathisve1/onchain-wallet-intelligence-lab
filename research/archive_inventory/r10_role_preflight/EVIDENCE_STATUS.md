# R10 STS-only preflight evidence status

Canonical run `31372438333` completed successfully from `main` at dispatch commit `8316f05f8fdfd444073e69e292cb89766ac89d7b` using the dedicated R10 role. The minimized artifact independently verifies `STS_IDENTITY_MATCH`, one workflow attempt, one explicit `sts:GetCallerIdentity` call, and zero S3 requests.

The preflight release is consumed and rerun remains forbidden. This evidence does not install or authorize the R10 data workflow, does not open any S3/object request, and does not authorize wallet ranking, PnL/alpha interpretation, copyability analysis, market-data ingestion, or any trading/capital action.

The next stage is a separate data-workflow implementation/release path under the already approved six-object R10 envelope.
