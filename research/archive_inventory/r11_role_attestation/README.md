# R11 operator attestation

This directory records minimized operator evidence for the dedicated R11 IAM role after the canonical R11 implementation merge. It binds the installed role to the canonical trust policy, exact 72-object persistent permission allowlist, session-duration limit and closed downstream gates.

The attestation is not an STS preflight, does not authorize any S3 request, and does not create an R11 execution release. A separately reviewed S3-denied STS-only preflight remains mandatory before any R11 data execution path can be released.
