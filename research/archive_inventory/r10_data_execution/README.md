# R10 bounded six-hour data workflow

This stage installs the R10 data workflow after the dedicated-role STS-only preflight was independently verified and consumed. Installation alone does not authorize a data run: a separate execution release candidate and a later canonical single-use activation are still required before AWS OIDC or any S3 object request may occur.

The original frozen data-workflow candidate remains immutable. The installed workflow is a narrow, non-scope-expanding binding adjustment because the frozen candidate predated the final canonical locations and field shapes of the operator-role attestation and STS-preflight evidence. The installed workflow points to those actual canonical evidence files and additionally requires the consumed-preflight record before it can reach OIDC.

The consumed STS-only preflight workflow is retired from `.github/workflows/` so there is only one active R10 OIDC workflow route. The installed data workflow keeps the same trust-bound workflow name, a 900-second role session, exact-six `s3:GetObject` session scope, one request per object, zero S3 retries, exact Requester Pays/integrity checks in the collector, and the approved six-hour compressed/decompressed byte caps.

This stage creates no S3 request, downloads no object bytes, creates no wallet-feature rows, ranks no wallets, performs no PnL/alpha or copyability analysis, and opens no paper/shadow/live/leverage/capital authority. The next gate is a separate inert R10 data execution release candidate.
