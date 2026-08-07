from __future__ import annotations

from dataclasses import dataclass
import re

from signature_backend_adapter import adapt_der_signature, adapt_p1363_signature

_ADDRESS = re.compile(r"^0x[0-9a-f]{40}$")


@dataclass(frozen=True)
class BackendConfig:
    provider: str
    key_version: str
    algorithm: str
    encoding: str
    expected_signer_address: str
    digest_mode: str

    def validate(self) -> None:
        if not self.provider or not self.algorithm:
            raise ValueError("backend:identity")
        if not self.key_version or self.key_version.lower() in {"latest", "current", "primary"}:
            raise ValueError("backend:key_version_not_immutable")
        if self.encoding not in {"DER", "P1363"}:
            raise ValueError("backend:encoding")
        if self.digest_mode not in {"EXACT_32_BYTE_PREHASHED", "PROVIDER_DIGEST_FIELD"}:
            raise ValueError("backend:digest_mode")
        if _ADDRESS.fullmatch(self.expected_signer_address.lower()) is None:
            raise ValueError("backend:signer_address")


def adapt_candidate_signature(config: BackendConfig, digest: bytes, signature_bytes: bytes) -> dict:
    """
    Offline provider compatibility boundary. It accepts captured signature bytes
    only; it performs no provider/network call and has no credential surface.
    """
    config.validate()
    if not isinstance(digest, (bytes, bytearray)) or len(digest) != 32:
        raise ValueError("backend:digest_length")

    if config.encoding == "DER":
        return adapt_der_signature(signature_bytes, bytes(digest), config.expected_signer_address)
    return adapt_p1363_signature(signature_bytes, bytes(digest), config.expected_signer_address)
