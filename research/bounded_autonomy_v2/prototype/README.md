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
- human-only upward execution-state transitions.

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

Local construction verification before upload executed against the hardened prototype:

```text
python -m unittest -v test_bounded_autonomy.py
29 tests
PASS
```

The matching trade-intent and trade-permit JSON Schemas were also checked locally as Draft 2020-12 schemas with valid entry/reduce/cancel fixtures. A cancel fixture containing invented economic fields was correctly rejected.

The hardened regression set specifically verifies that entry-only controls cannot accidentally disable safety-preserving cancel/reduce-only paths, while cancel targets must still be strategy-owned and reduce-only quantities/sides must remain bounded by the reconciled position.

That local run is engineering feedback only, not canonical repository CI evidence. This branch deliberately does not touch the repository manifest or open a PR while the parallel data/evidence lane is active.

Before later promotion this exact branch must be reconciled onto stable canonical `main`, added to the repository manifest, tested by canonical CI, and reviewed in clean context.