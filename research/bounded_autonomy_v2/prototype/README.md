# Pure control-plane prototype

This prototype is deliberately incapable of network access, signing or secret handling.

It uses only Python standard-library primitives to exercise the design invariants before any venue adapter exists:

- canonical JSON hashing helpers;
- strict signed/unsigned decimal parsing;
- risk-envelope validation;
- fail-closed intent evaluation;
- AI veto/timeout behavior for risk-increasing entries;
- a model-independent `DETERMINISTIC_SAFETY` mode for cancel/reduce-only actions;
- slippage/notional/exposure/loss gates for risk-increasing entries;
- reduce-only validation against the reconciled signed position;
- strategy-owned cancel validation without invented quantity/price fields;
- cancellation and reduction remaining available when entry loss/exposure/rate-reserve gates are hit;
- deterministic cloid derivation for new strategy orders;
- abstract IOC/cancel action compilation;
- single-use permit registry behavior;
- human-only upward execution-state transitions;
- explicit intent -> policy -> permit -> sign -> submit -> acknowledgement/fill reconciliation states;
- partial fills remaining unresolved until terminal;
- crash-after-sign uncertainty becoming `POSSIBLY_SUBMITTED`, never a blind retry;
- blocked intents becoming terminal so a normal policy reject cannot deadlock future risk decisions;
- duplicate permit/action IDs and impossible state transitions failing closed.

There is intentionally no:

```text
urllib / requests / websocket
Hyperliquid SDK import
private key
signature function
/exchange post
wallet creation
mainnet/testnet connection
```

Local construction verification executed against the hardened control and reconciliation prototypes:

```text
python -m unittest discover -v
40 tests
PASS
```

The matching trade-intent and trade-permit JSON Schemas were also checked locally as Draft 2020-12 schemas with valid entry/reduce/cancel fixtures. A cancel fixture containing invented economic fields was correctly rejected.

The cross-document `validate_design.py` validator is included for later branch/CI execution. It checks action/mode parity, all-false authorizations, parent-lane immutability, AI authority restrictions, deterministic safety semantics, reconciliation-state parity and the absence of network/signing libraries from the pure prototype.

These local runs are engineering feedback only, not canonical repository CI evidence. This branch deliberately does not touch the repository manifest or open a PR while the parallel data/evidence lane is active.

Before later promotion this exact branch must be reconciled onto stable canonical `main`, added to the repository manifest, tested by canonical CI, and reviewed in clean context.