# R10 dedicated-role STS-only preflight

This stage installs the frozen R10 preflight workflow byte-for-byte from the reviewed implementation candidate and records its contract. Installation alone does not authorize a workflow dispatch.

The workflow is deliberately fail-closed before AWS OIDC: a separate single-use canonical preflight release must exist, the dispatch must be manual from `main`, and prior/rerun history is rejected before credentials are configured. The assumed-role session is 900 seconds and carries an inline session policy that explicitly denies `s3:*` on all resources.

The only explicit AWS CLI call in the preflight is `aws sts get-caller-identity --output json`. No S3 command, Requester Pays request, object access, decompression, data workflow installation, wallet ranking, PnL/alpha interpretation, copyability analysis or trading/capital authority is opened by this stage.

`R10_STS_PREFLIGHT_RELEASE_CANDIDATE.json` remains deliberately inert and immutable: its dispatch and STS authorization fields remain false and it has no activation timestamp or anchor commit. The separate runtime file `research/archive_inventory/r10_runtime/R10_STS_PREFLIGHT_RELEASE.json` now releases exactly one future manual `main` dispatch for the STS-only preflight. Reruns remain forbidden, the release is not yet consumed, and all S3/data/downstream/trading authority remains closed until later separately governed stages.
