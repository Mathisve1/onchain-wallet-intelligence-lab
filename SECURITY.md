# Security

Do not commit:

- private keys or seed phrases;
- Hyperliquid API-wallet credentials;
- exchange API secrets;
- `.env` files;
- OAuth refresh tokens;
- cloud service credentials;
- personally identifying wallet-owner claims without a lawful public source.

All current network scripts are read-only and capability-allowlisted. Any future
change that imports signing libraries, calls an exchange/action endpoint or
creates an order must fail CI unless a separate governance decision explicitly
opens that development scope. No such decision currently exists.
