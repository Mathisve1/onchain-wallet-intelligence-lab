# R6A research conclusion

R6A completed successfully on canonical `main` at `161b3ff76c3a1903a633f4b3317386ef1cc7b38b` in workflow run `31328268134`.

The exact R5-bound legacy object was retrieved once with Requester Pays. Transport and integrity checks passed, there were zero retries and zero redirects, and the frozen compressed/decompressed byte expectations matched.

## Empirical result

All `162,815` nonempty records retained the R5-proven `[string, object]` shape.

For the leading string:

- `162,815 / 162,815` have length 42.
- `162,815 / 162,815` match `0x` followed by 40 hexadecimal characters.
- `162,815 / 162,815` match the lowercase `0x` + 40-hex form.
- `0 / 162,815` fail the address-shape test.

No leading string value, wallet address, address hash, distinct-address set, record payload, compressed object or decompressed payload was retained.

## Interpretation with R6

R6 had already established, from historical official Hyperliquid node/API/SDK evidence, a **high-confidence** inference that the leading string in legacy `[string, fill_object]` records is the Hyperliquid user/onchain address associated with the fill.

R6A now independently confirms that every leading string in the exact legacy object has the documented 42-character lowercase `0x`-prefixed hexadecimal address shape.

The combined conclusion is therefore:

**`HYPERLIQUID_USER_ADDRESS` is supported by convergent high-confidence static provenance plus 100% lexical-shape evidence.**

This is strong enough to use as the working semantic contract for a separately preregistered wallet-reconstruction research stage, but it is still not direct proof of the unpublished serializer variable name/type. R6A itself does **not** authorize retaining addresses, reconstructing wallets, clustering entities, computing copyability/PnL, ingesting market data or trading.

## Release state

R6A release-002 is consumed. The aggregate one-GetObject budget across the R6A release chain is exhausted. No rerun or future R6A dispatch is authorized.

The next correct gate is a new, explicit wallet-reconstruction preregistration with its own data-retention boundary, validation plan and human approval before any address values are retained.
