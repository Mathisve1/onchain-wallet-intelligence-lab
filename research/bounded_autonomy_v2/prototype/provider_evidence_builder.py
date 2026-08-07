from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from provider_fixture_harness import BackendConfig, adapt_candidate_signature
from public_key_adapter import parse_secp256k1_spki
from signature_backend_adapter import SignatureAdapterError

ROOT = Path(__file__).resolve().parents[1]
MUTABLE_KEY_MARKERS = {"latest", "current", "primary"}
MIN_LATENCY_SAMPLES_FOR_COMPATIBLE_CANDIDATE = 100


class ProviderEvidenceError(ValueError):
    pass


def _b64(value: str, label: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ProviderEvidenceError(f"{label}:invalid_base64") from exc
    if not raw:
        raise ProviderEvidenceError(f"{label}:empty")
    return raw


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _percentile(samples: list[float], probability: float) -> float:
    if not samples:
        raise ProviderEvidenceError("latency:no_samples")
    ordered = sorted(float(value) for value in samples)
    if any(not math.isfinite(value) or value < 0 for value in ordered):
        raise ProviderEvidenceError("latency:invalid_sample")
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def _fixture(fixtures_path: Path, fixture_id: str) -> dict[str, Any]:
    document = json.loads(fixtures_path.read_text(encoding="utf-8"))
    matches = [row for row in document.get("fixtures", []) if row.get("id") == fixture_id]
    if len(matches) != 1:
        raise ProviderEvidenceError("fixture:not_unique")
    return matches[0]


def _mutate_digest(digest: bytes) -> bytes:
    return bytes([digest[0] ^ 1]) + digest[1:]


def build_sanitized_evidence(capture: dict[str, Any], fixtures_path: Path | None = None) -> dict[str, Any]:
    if capture.get("schema_version") != "0.2-local-ephemeral":
        raise ProviderEvidenceError("capture:schema")
    resource = str(capture.get("key_resource_version", ""))
    if len(resource) < 8 or resource.lower() in MUTABLE_KEY_MARKERS:
        raise ProviderEvidenceError("capture:key_version_not_immutable")

    fixtures_path = fixtures_path or (ROOT / "PROVIDER_PARITY_FIXTURES.json")
    fixture = _fixture(fixtures_path, capture["fixture_id"])
    digest = bytes.fromhex(fixture["eip712_digest"])
    if len(digest) != 32:
        raise ProviderEvidenceError("fixture:digest_length")

    public_key = _b64(capture["public_key_spki_base64"], "capture:public_key")
    _, derived_address = parse_secp256k1_spki(public_key)
    raw_signature = _b64(capture["raw_signature_base64"], "capture:signature")

    digest_mode = str(capture["digest_mode"])
    config = BackendConfig(
        provider=str(capture["provider"]),
        key_version=resource,
        algorithm=str(capture["algorithm"]),
        encoding=str(capture["signature_encoding"]),
        expected_signer_address=derived_address,
        digest_mode=digest_mode,
    )

    normalized = None
    recovered = None
    exact_pass = False
    double_hash_detected = False
    encoding_unresolved = False
    try:
        normalized = adapt_candidate_signature(config, digest, raw_signature)
        recovered = derived_address
        exact_pass = True
    except (SignatureAdapterError, ValueError) as exact_error:
        text = str(exact_error)
        if text.startswith("der:") or text.startswith("p1363:") or "encoding" in text:
            encoding_unresolved = True
        try:
            adapt_candidate_signature(config, hashlib.sha256(digest).digest(), raw_signature)
            double_hash_detected = True
        except Exception:
            pass

    wrong_digest_rejected = False
    wrong_signer_rejected = False
    if exact_pass:
        try:
            adapt_candidate_signature(config, _mutate_digest(digest), raw_signature)
        except Exception:
            wrong_digest_rejected = True
        wrong_config = BackendConfig(
            provider=config.provider,
            key_version=config.key_version,
            algorithm=config.algorithm,
            encoding=config.encoding,
            expected_signer_address="0x" + "11" * 20,
            digest_mode=config.digest_mode,
        )
        try:
            adapt_candidate_signature(wrong_config, digest, raw_signature)
        except Exception:
            wrong_signer_rejected = True

    samples = [float(value) for value in capture.get("latency_samples_ms", [])]
    latency = {
        "sample_count": len(samples),
        "p50": _percentile(samples, 0.50),
        "p75": _percentile(samples, 0.75),
        "p90": _percentile(samples, 0.90),
        "p95": _percentile(samples, 0.95),
        "p99": _percentile(samples, 0.99),
    }

    revoke_tested = capture.get("key_disable_revoke_tested") is True
    if double_hash_detected:
        decision = "DIGEST_TRANSFORMATION_INCOMPATIBLE"
    elif encoding_unresolved:
        decision = "SIGNATURE_ENCODING_UNRESOLVED"
    elif not exact_pass:
        decision = "RECOVERY_FAILED"
    elif not (wrong_digest_rejected and wrong_signer_rejected):
        decision = "OPERATIONAL_NO_GO"
    elif not revoke_tested or len(samples) < MIN_LATENCY_SAMPLES_FOR_COMPATIBLE_CANDIDATE:
        decision = "INCOMPLETE_EVIDENCE"
    else:
        decision = "COMPATIBLE_CANDIDATE"

    return {
        "schema_version": "0.3",
        "provider": str(capture["provider"]),
        "service": str(capture["service"]),
        "region_or_location": str(capture["region_or_location"]),
        "key_resource_version_hash": _sha(resource.encode("utf-8")),
        "public_key_sha256": _sha(public_key),
        "expected_signer_address": derived_address,
        "curve": "secp256k1",
        "algorithm": str(capture["algorithm"]),
        "request_mode": str(capture["request_mode"]),
        "digest_mode": digest_mode,
        "signature_encoding": str(capture["signature_encoding"]),
        "fixture_id": str(capture["fixture_id"]),
        "input_digest_sha256": _sha(digest),
        "raw_signature_sha256": _sha(raw_signature),
        "normalized_signature": normalized,
        "recovered_address": recovered,
        "exact_digest_recovery_pass": exact_pass,
        "wrong_digest_rejected": wrong_digest_rejected,
        "wrong_signer_rejected": wrong_signer_rejected,
        "double_hash_signature_detected": double_hash_detected,
        "key_disable_revoke_tested": revoke_tested,
        "latency_ms": latency,
        "software_versions": dict(capture.get("software_versions", {})),
        "terminal_decision": decision,
        "provider_network_call_authorized_after_evidence": False,
        "testnet_action_authorized": False,
        "live_action_authorized": False,
    }


def evidence_json(capture: dict[str, Any], fixtures_path: Path | None = None) -> str:
    return json.dumps(build_sanitized_evidence(capture, fixtures_path), indent=2, sort_keys=True) + "\n"
