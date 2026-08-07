# Pure control-plane prototype

This prototype is deliberately incapable of network access, signing or secret handling.

It uses only Python standard-library primitives to exercise the design invariants before any venue adapter exists:

- canonical JSON hashing helpers;
- strict decimal parsing;
- risk-envelope validation;
- fail-closed intent evaluation;
- AI veto/timeout behavior;
- slippage/notional/exposure/loss gates;
- deterministic cloid derivation;
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

Local construction verification before upload executed:

```text
python -m unittest -v test_bounded_autonomy.py
15 tests
PASS
```

That local run is engineering feedback only, not canonical repository CI evidence. This branch deliberately does not touch the repository manifest or open a PR while the parallel data/evidence lane is active.

Before later promotion this exact branch must be rebased onto stable canonical `main`, added to the repository manifest, tested by canonical CI, and reviewed in clean context.