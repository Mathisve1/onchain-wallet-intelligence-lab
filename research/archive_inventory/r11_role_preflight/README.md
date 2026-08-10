# R11 STS-only role preflight

This stage installs the exact frozen R11 role-preflight workflow after canonical operator attestation. The route remains inert until a separate single-use preflight release and separate canonical activation are merged.

The preflight may assume only the dedicated R11 role and execute exactly one `aws sts get-caller-identity` call. Its inline session policy explicitly denies every `s3:*` action on every resource. No Requester Pays request, object download, decompression, wallet-feature processing or data-workflow execution is authorized here.

The 72-object R11 data workflow remains uninstalled. Wallet ranking, shortlisting, PnL/alpha, copyability, enrichment, clustering, market-data/strategy work and all trading/leverage/capital authority remain closed.
