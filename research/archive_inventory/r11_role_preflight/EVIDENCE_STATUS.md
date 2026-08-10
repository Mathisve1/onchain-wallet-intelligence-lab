# R11 STS-only preflight evidence status

Canonical run `31433889087` completed successfully from `main` at dispatch commit `efad3f278e458a5c35fbfcc11de2b97bbe7cb388` using the dedicated R11 role. The minimized artifact independently verifies the expected account and assumed-role session, one workflow attempt, one explicit `sts:GetCallerIdentity` call, and zero S3 requests or object bytes downloaded.

The artifact provider digest `sha256:1de9b92dba9ee74152166e4a9890a5a788b36f104499c9323b66e2aa9374eb79` matches the independently downloaded ZIP. Its internal SHA-256 ledger matches all three retained raw evidence files exactly.

The preflight release is consumed and rerun remains forbidden. This evidence does not install or authorize the R11 72-hour data workflow, does not open Requester Pays or any S3/object request, and does not authorize historical expansion beyond the approved three days, ranking, shortlisting, PnL/alpha interpretation, copyability, enrichment, clustering, market-data/strategy work, or any trading/capital action.

The next stage is a separate inert data-workflow installation and release path under the already approved exact 72-object R11 envelope.
