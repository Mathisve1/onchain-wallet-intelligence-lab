# Rejected Pre-Run Predecessors

These attempts are immutable negative engineering evidence. Neither produced an accepted workflow result, public-route result, market result or authorization.

## PR #1 — first attempt

Disposition: `REJECTED_PRE_RUN_TEST_DESIGN_DEFECT`.

The negative test rejected the substring `private_key` while the collector correctly used the negative audit field `private_keys_used=false`. Any resulting CI failure would therefore describe an overbroad test, not a forbidden capability.

## PR #2 — reviewed attempt

Disposition: `REJECTED_PRE_RUN_AST_TEST_DESIGN_DEFECT`.

The AST test rejected `authorization` inside legitimate negative contract/evidence fields such as `authorization_header_used=false`. Again, that was a test-design failure rather than a network or security finding.

## Canonical successor rule

The canonical successor starts from main commit `c08f7dc9419857770e53cd760f447394ecfa1bae` and does not repair either attempt in place. Its tests inspect actual imports, calls, request constructors, workflow permissions and headers without banning required negative evidence names.

The rejected branches must not be merged or cited as successful technical evidence. No market data was ingested; `empirical_result=null`; integration, paper, shadow, live, leverage and capital allocation remain unauthorized.
