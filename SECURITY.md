# Security

## Forbidden material

Do not commit or provide to the current system:

- private keys or seed phrases;
- Hyperliquid API-wallet credentials;
- exchange API secrets;
- `.env` files;
- OAuth refresh tokens;
- cloud service credentials;
- authorization headers;
- signed actions or order payloads; or
- personally identifying wallet-owner claims without a lawful public source.

## Public probe capability boundary

`HL-PUBLIC-PROBE-001R1` may contact only the three origins frozen in
`research/wallet_copyability/PROBE_CONTRACT.json`.

The script:

- rejects cross-origin redirects;
- rejects responses beyond the frozen byte ceiling;
- imports only allowlisted standard-library modules;
- contains no signing or credential-reading capability;
- cannot call Hyperliquid's `/exchange` action endpoint;
- writes no raw response bodies;
- retains no response values such as prices, sizes or account balances; and
- runs in GitHub Actions with `contents: read` and checkout credential
  persistence disabled.

The workflow artifact contains only structural probe evidence. It is still
private repository evidence and must be handled accordingly.

## Change control

Any future change that introduces a new network origin, signing library,
credential source, action endpoint, order method, withdrawal method or raw
response retention must fail CI unless a separate explicit governance decision
opens that exact scope. No such decision exists.
