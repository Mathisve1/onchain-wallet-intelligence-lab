# Live data collection pilot

Forward-only, read-only observation of the public Hyperliquid venue. This
directory holds the governance record for that pilot; the code it governs is
`src/live_data` (deterministic core) and
`research/wallet_copyability/live_data_collector` (network transports).

| File | Purpose |
|---|---|
| `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.json` | The binding frozen contract. |
| `L1_LIVE_DATA_COLLECTION_PREREGISTRATION.md` | The same contract in prose, with reasoning. |
| `HUMAN_APPROVAL_TEMPLATE.md` | The exact text an owner must send to approve. |
| `STATUS.md` | Current state and the next gate. |

Nothing in this directory executes.
`governance/validate_l1_live_data_preregistration.py` checks that the contract
stays consistent with the code it claims to describe and that no gate has
silently opened.
