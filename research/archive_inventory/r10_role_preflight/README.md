# R10 dedicated-role STS-only preflight

This stage installs the frozen R10 preflight workflow byte-for-byte from the reviewed implementation candidate and records its contract. Installation alone does not authorize a workflow dispatch.

The workflow is deliberately fail-closed before AWS OIDC: a separate single-use canonical preflight release must exist, the dispatch must be manual from `main`, and prior/rerun history is rejected before credentials are configured. The assumed-role session is 900 seconds and carries an inline session policy that explicitly denies `s3:*` on all resources.

The only explicit AWS CLI call in the preflight is `aws sts get-caller-identity --output json`. No S3 command, Requester Pays request, object access, decompression, data workflow installation, wallet ranking, PnL/alpha interpretation, copyability analysis or trading/capital authority is opened by this stage.

The next gate is a separate inert preflight release candidate followed by a canonical single-use release. Until that release exists, the installed workflow cannot pass its pre-OIDC release gate.
