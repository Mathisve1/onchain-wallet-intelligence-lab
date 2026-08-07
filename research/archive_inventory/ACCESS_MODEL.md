# Access model

Hyperliquid documents requester-paid historical data. AWS Requester Pays requires authenticated requests and an explicit acknowledgement of charges. A later `ListObjectsV2` adapter must use `RequestPayer=requester` and record the charged-request response indication when returned.

The current preregistration binds no AWS account, role, access key, profile, OIDC identity or billing account. No credential belongs in this repository or chat.

Future access states are `LISTING_AVAILABLE_REQUESTER_CHARGED`, `LISTING_AVAILABLE_NOT_MARKED_CHARGED`, `ACCESS_DENIED_AUTHENTICATED`, `REGION_OR_ENDPOINT_UNRESOLVED`, or `AUTHENTICATION_FAILURE`.

The anonymous 403 observed in the public probe is not proof that Requester Pays is the only restriction. An authenticated canary must distinguish the cause.
