# R11A inert implementation

This directory implements the already merged R11A identity-and-boundary preregistration. Its current lifecycle state is `IMPLEMENTED_AWAITING_OWNER_APPROVAL_NO_EXECUTION` only after the exact implementation seal and CI pass.

The implementation keeps four layers separate: raw source observation, archive block, protocol matched trade and wallet user fill. It reproduces the historical `wallet + typed tid` projection only to locate and classify the original R11 repeat groups. It never treats that weak key as canonical identity and never suppresses an observation.

The code contains:

- strict typed JSON parsing and versioned identity serialization;
- explicit block, trade and wallet-fill identities;
- the nine-class diagnostic taxonomy;
- fixed-width partition routing and bounded external sorting;
- exact two-pass local parsing with source-count and commitment comparison;
- a pure explicit-write activity tracker that cannot mutate on reads;
- atomic scientific-output packaging with empty fail-closed cap terminals;
- frozen limits, dependency declaration, successor-role candidate and workflow candidate.

The workflow remains under `r11a_implementation/workflows/`, not `.github/workflows`. The runtime release path does not exist. The collector checks for a future exact single-use release before network execution. This implementation stage performs no IAM, OIDC, STS or S3 operation and authorizes no repair, wallet features, ranking, PnL/alpha, copyability, R11 closure or R12 promotion.

The resource report deliberately distinguishes bounded failure from guaranteed success. The known source can be processed within the declared design under representative integer-`tid` index sizes, but the unknown repeat, schema and legacy-string-key volumes can still trigger a preregistered incomplete or artifact-cap terminal. No sampling or silent cap increase is permitted.
