from __future__ import annotations

from decimal import Decimal
import hashlib
import hmac
import msgpack

# TEST-ONLY independent oracle. This file is forbidden from production signer use.
# It exists to prove parity against pinned official Hyperliquid SDK fixtures.

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    55066263022277343669578718895168534326250603453777594175500187360389116729240,
    32670510020758816978083085130507043184471273380659243275938904335757337482424,
)
_MASK = (1 << 64) - 1
_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]


def _rol(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (64 - shift))) & _MASK if shift else value


def _keccak_f(state: list[int]) -> list[int]:
    state = list(state)
    for rc in _RC:
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(state[x + 5 * y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y])
        state[0] ^= rc
    return state


def keccak256(data: bytes) -> bytes:
    """Ethereum Keccak-256. Deliberately not hashlib.sha3_256."""
    rate = 136
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != rate - 1:
        padded.append(0)
    padded.append(0x80)
    state = [0] * 25
    for offset in range(0, len(padded), rate):
        block = padded[offset : offset + rate]
        for index, byte in enumerate(block):
            state[index // 8] ^= byte << (8 * (index % 8))
        state = _keccak_f(state)
    out = bytearray()
    while len(out) < 32:
        for index in range(rate):
            out.append((state[index // 8] >> (8 * (index % 8))) & 0xFF)
            if len(out) == 32:
                break
        if len(out) < 32:
            state = _keccak_f(state)
    return bytes(out)


def float_to_wire(value: float) -> str:
    """Byte-behavior fixture matching pinned SDK 0.24.0, including its current negative-zero result."""
    rounded = f"{value:.8f}"
    if abs(float(rounded) - value) >= 1e-12:
        raise ValueError("float_to_wire causes rounding")
    if rounded == "-0":
        rounded = "0"
    return f"{Decimal(rounded).normalize():f}"


def order_wire(
    asset: int,
    is_buy: bool,
    size: float,
    price: float,
    reduce_only: bool,
    tif: str,
    cloid: str | None = None,
) -> dict:
    # Insertion order is part of the msgpack/signature contract.
    wire = {
        "a": asset,
        "b": is_buy,
        "p": float_to_wire(price),
        "s": float_to_wire(size),
        "r": reduce_only,
        "t": {"limit": {"tif": tif}},
    }
    if cloid is not None:
        wire["c"] = cloid
    return wire


def order_action(wires: list[dict]) -> dict:
    # Insertion order is part of the msgpack/signature contract.
    return {"type": "order", "orders": wires, "grouping": "na"}


def action_hash(action: dict, vault_address: str | None, nonce: int, expires_after: int | None) -> bytes:
    data = msgpack.packb(action)
    data += int(nonce).to_bytes(8, "big")
    if vault_address is None:
        data += b"\x00"
    else:
        raw = bytes.fromhex(vault_address[2:] if vault_address.startswith("0x") else vault_address)
        if len(raw) != 20:
            raise ValueError("vault address length")
        data += b"\x01" + raw
    if expires_after is not None:
        data += b"\x00" + int(expires_after).to_bytes(8, "big")
    return keccak256(data)


def _u256(value: int) -> bytes:
    return int(value).to_bytes(32, "big")


def _address(address: str) -> bytes:
    raw = bytes.fromhex(address[2:] if address.startswith("0x") else address)
    if len(raw) != 20:
        raise ValueError("address length")
    return b"\x00" * 12 + raw


def agent_digest(connection_id: bytes, is_mainnet: bool) -> bytes:
    domain_type = keccak256(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    domain = keccak256(
        domain_type
        + keccak256(b"Exchange")
        + keccak256(b"1")
        + _u256(1337)
        + _address("0x" + "00" * 20)
    )
    agent_type = keccak256(b"Agent(string source,bytes32 connectionId)")
    source = b"a" if is_mainnet else b"b"
    struct_hash = keccak256(agent_type + keccak256(source) + connection_id)
    return keccak256(b"\x19\x01" + domain + struct_hash)


def _inv(value: int, modulus: int) -> int:
    return pow(value, -1, modulus)


def _add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if left == right:
        if y1 == 0:
            return None
        slope = (3 * x1 * x1) * _inv(2 * y1, P) % P
    else:
        slope = (y2 - y1) * _inv((x2 - x1) % P, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def _mul(scalar: int, point=G):
    out = None
    addend = point
    while scalar:
        if scalar & 1:
            out = _add(out, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return out


def _rfc6979(private_key: int, digest_int: int) -> int:
    private_bytes = private_key.to_bytes(32, "big")
    digest_bytes = (digest_int % N).to_bytes(32, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + private_bytes + digest_bytes, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + private_bytes + digest_bytes, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        candidate_bytes = b""
        while len(candidate_bytes) < 32:
            v = hmac.new(k, v, hashlib.sha256).digest()
            candidate_bytes += v
        candidate = int.from_bytes(candidate_bytes, "big")
        if 1 <= candidate < N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign_digest(private_key: int, digest: bytes) -> dict:
    digest_int = int.from_bytes(digest, "big")
    nonce = _rfc6979(private_key, digest_int)
    rx, ry = _mul(nonce)
    r = rx % N
    s = (_inv(nonce, N) * (digest_int + r * private_key)) % N
    recovery_id = (ry & 1) | (2 if rx >= N else 0)
    if s > N // 2:
        s = N - s
        recovery_id ^= 1
    return {"r": "0x" + format(r, "x"), "s": "0x" + format(s, "x"), "v": recovery_id + 27}


def sign_l1(
    private_key: int,
    action: dict,
    vault_address: str | None,
    nonce: int,
    expires_after: int | None,
    is_mainnet: bool,
) -> dict:
    connection_id = action_hash(action, vault_address, nonce, expires_after)
    return sign_digest(private_key, agent_digest(connection_id, is_mainnet))


def public_address(private_key: int) -> str:
    x, y = _mul(private_key)
    return "0x" + keccak256(x.to_bytes(32, "big") + y.to_bytes(32, "big"))[-20:].hex()


def recover_address(digest: bytes, r: int, s: int, v: int) -> str:
    recovery_id = v - 27
    if recovery_id not in range(4):
        raise ValueError("recovery id")
    x = r + (recovery_id // 2) * N
    if x >= P:
        raise ValueError("recovery x")
    alpha = (pow(x, 3, P) + 7) % P
    beta = pow(alpha, (P + 1) // 4, P)
    y = beta if (beta & 1) == (recovery_id & 1) else P - beta
    point_r = (x, y)
    if _mul(N, point_r) is not None:
        raise ValueError("recovery subgroup")
    digest_int = int.from_bytes(digest, "big")
    digest_point = _mul(digest_int % N, G)
    negative_digest_point = (digest_point[0], (-digest_point[1]) % P)
    public_key = _mul(_inv(r, N), _add(_mul(s, point_r), negative_digest_point))
    return "0x" + keccak256(public_key[0].to_bytes(32, "big") + public_key[1].to_bytes(32, "big"))[-20:].hex()
