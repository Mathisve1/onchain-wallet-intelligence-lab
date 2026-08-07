# AI runtime boundary — not a prompt-controlled wallet

Status: design only. No model is connected to a signer or venue action endpoint.

## Design objective

The goal is to encode the useful parts of a disciplined human trader's review process without granting a probabilistic model direct authority over money movement or safety invariants.

A long system prompt is therefore treated as **decision-support logic**, not as a security boundary. Security-critical constraints exist in typed schemas and deterministic services outside the model.

## What the AI receives

The critic receives a versioned structured context snapshot containing only fields necessary for the registered research question, for example:

- exact source-signal reference and first-seen timestamp;
- deterministic eligibility decision and reason codes;
- deterministic maximum position/notional and slippage envelope;
- point-in-time source-wallet/style features supplied by the parent research lane;
- follower-EV/model summaries produced by deterministic/statistical services;
- fresh market microstructure summaries and data-age metadata;
- concentration, drift and anomaly flags;
- open-position and strategy-order summaries relevant to the candidate;
- hashes/IDs linking every derived value to canonical evidence.

The AI does not calculate the canonical ledger, P&L, risk cap, nonce, cloid, action bytes or account balance itself.

## What the AI does not receive

Never place in model context:

- seed phrase;
- master private key;
- API-wallet private key;
- signer handle or KMS/HSM raw signing capability;
- generic exchange/RPC write credential;
- withdrawal destination allowlist secrets;
- arbitrary executable code from an external source;
- untrusted webpages/token metadata as system instructions;
- hidden policy override tokens;
- raw operational secrets from logs.

## Untrusted-data rule

Wallet labels, token names, social posts, webpages, contract metadata, provider errors and free text are **data**, never instructions.

If text-derived features are later useful:

1. raw text enters a quarantined parser/classifier stage;
2. execution-critical model context receives only an explicitly typed representation;
3. original text is referenced by evidence ID/hash rather than concatenated into privileged instructions where possible;
4. no external text can introduce tool calls, policies or action types;
5. model output still passes deterministic policy after the AI call.

## Model output ceiling

The primary critic schema contains no fields for:

- quantity;
- order price;
- slippage;
- leverage;
- account;
- signer;
- recipient;
- raw exchange action;
- policy mutation;
- stage promotion.

It can return only:

```text
PASS or VETO
confidence
risk codes
evidence references
missing-evidence codes
```

The deterministic system then either retains the original bounded candidate or rejects it. AI cannot mutate the candidate into a riskier one.

## Timeouts and model outages

For an entry arm where the frozen human policy requires an AI critic:

```text
AI timeout/error -> SKIP
```

There is no automatic fallback from `AI_REQUIRED` to a less restrictive entry mode.

Safety-preserving `DETERMINISTIC_SAFETY` cancel/reduce-only paths do not require the model. This prevents an AI/provider outage from disabling deterministic risk reduction.

## Model versioning

Every AI assessment must bind to:

- exact model identifier/version available from the provider/runtime;
- prompt/policy template hash;
- structured-context schema version;
- context snapshot hash;
- generated timestamp;
- assessment output hash.

A prompt or model change is a new experimental treatment. It cannot silently replace the model version used by an accepted result.

## Human-trader playbook representation

Rather than one giant prose prompt, the playbook should eventually be decomposed into versioned modules, for example:

1. source-wallet integrity checklist;
2. style-drift checklist;
3. copyability/latency checklist;
4. manipulation/coordination checklist;
5. market-state checklist;
6. missing-evidence checklist;
7. skeptic/counterargument checklist;
8. final veto mapping to registered risk codes.

Each module should cite deterministic fields and evidence IDs. Where a rule can be expressed deterministically, it belongs outside the LLM.

## Multi-agent use

Multiple agents are a research option, not a default safety feature. If later evaluated:

- agents cannot vote to expand eligibility;
- a majority cannot override a deterministic block;
- disagreement is retained as evidence;
- the final execution decision still passes one deterministic policy firewall;
- extra latency and model cost are included in follower economics;
- the comparison is preregistered to avoid selecting the best-looking agent ensemble after the fact.

## Logging

Retain structured model evidence sufficient for reproducibility without storing secrets:

- request schema/version;
- sanitized context hash and evidence refs;
- model ID/version;
- prompt/playbook hash;
- latency;
- output object and hash;
- parsing/validation outcome;
- timeout/error class;
- final deterministic policy result.

Natural-language chain-of-thought is neither required nor a canonical execution artifact. The canonical audit trail is the structured input/output and deterministic decision record.