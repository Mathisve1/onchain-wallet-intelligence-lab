# Clean-context review — HL-AWS-OIDC-IDENTITY-001

Accepted canonical identity evidence is limited to AWS STS federation identity.

Verified independently from GitHub run `31250176507`, job `93085194965`, artifact `9019744292`:

- dispatch ref, dispatch SHA, reviewed commit and checked-out commit all bind to canonical main `f34786eafd3689b575bdd3d2ada932b8ce204a61`;
- GitHub OIDC role assumption succeeded for AWS account `630956766927`;
- `GetCallerIdentity` returned the exact expected assumed-role ARN;
- exactly one explicit STS identity call was made;
- the assumed session carried `Deny s3:*`;
- no S3 call or Requester Pays request occurred;
- the downloaded artifact ZIP SHA-256 independently matches GitHub's provider digest;
- retained internal file hashes match the workflow-produced evidence.

This attestation does not independently verify the role's persistent inline S3 permission policy. That remains user-confirmed until a separately approved S3 metadata canary exercises only the preregistered listing scope.

No market data, wallet result, trading authorization or capital authorization is created by this evidence.
