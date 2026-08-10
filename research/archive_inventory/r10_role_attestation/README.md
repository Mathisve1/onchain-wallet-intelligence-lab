# R10 dedicated-role operator attestation

This directory records the minimized operator evidence that the dedicated R10 IAM role was created in AWS account `630956766927` and that its installed trust and inline permission policies were read back and semantically matched to the canonical R10 policy files.

The attestation is deliberately separate from the immutable R10 implementation snapshot. The implementation snapshot remains an inert pre-execution record; this directory records the later real-world operator action without rewriting prior state.

This stage authorizes no R10 OIDC workflow, no R10 STS preflight, no S3 request, no object download, no decompression, no wallet ranking, no PnL/alpha interpretation, no copyability analysis and no trading or capital action. The next gate is a separately released, S3-denied STS-only preflight.

Raw shell transcripts, AWS credentials and session tokens are not retained. Only the fields needed to bind the observed role to the canonical trust and permission policy hashes are retained.
