#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import os
import socket
import subprocess
import sys
import unittest
import urllib.request
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class NetworkDenied(RuntimeError):
    pass


NETWORK_CLIENTS = frozenset(
    {
        "aws",
        "curl",
        "dig",
        "git",
        "gh",
        "host",
        "nc",
        "netcat",
        "nslookup",
        "scp",
        "sftp",
        "ssh",
        "wget",
    }
)


def deny(label: str) -> NetworkDenied:
    return NetworkDenied(f"R11A network-deny harness blocked: {label}")


def _audit(event: str, arguments: tuple[object, ...]) -> None:
    if event.startswith("socket."):
        raise deny(event)
    if event == "subprocess.Popen" and arguments:
        executable = os.path.basename(os.fspath(arguments[0])).lower()
        if executable in NETWORK_CLIENTS:
            raise deny(f"subprocess network client {executable}")


def _blocked(*_: object, **__: object) -> None:
    raise deny("socket, DNS, connect, send, or HTTP operation")


def install_network_deny() -> None:
    """Deny network creation at both audit and Python API boundaries."""

    sys.addaudithook(_audit)
    socket.socket = _blocked  # type: ignore[assignment]
    socket.socketpair = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.create_server = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    socket.gethostbyname = _blocked  # type: ignore[assignment]
    socket.gethostbyname_ex = _blocked  # type: ignore[assignment]
    socket.gethostbyaddr = _blocked  # type: ignore[assignment]
    urllib.request.urlopen = _blocked  # type: ignore[assignment]
    urllib.request.OpenerDirector.open = _blocked  # type: ignore[assignment]
    http.client.HTTPConnection.connect = _blocked  # type: ignore[assignment]
    http.client.HTTPSConnection.connect = _blocked  # type: ignore[assignment]

    original_popen = subprocess.Popen

    def guarded_popen(
        args: Sequence[str] | str,
        *popen_args: object,
        **popen_kwargs: object,
    ) -> subprocess.Popen[bytes]:
        first = args.split()[0] if isinstance(args, str) else os.fspath(args[0])
        executable = os.path.basename(first).lower()
        if executable in NETWORK_CLIENTS:
            raise deny(f"subprocess network client {executable}")
        return original_popen(args, *popen_args, **popen_kwargs)  # type: ignore[return-value]

    subprocess.Popen = guarded_popen  # type: ignore[assignment]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run R11A critical tests with process-level network denial"
    )
    parser.add_argument(
        "tests",
        nargs="*",
        default=(
            "tests.test_archive_inventory_r11a_corrective_r7",
            "tests.test_archive_inventory_r11a_corrective_r7_precedence",
            "tests.test_archive_inventory_r11a_post_approval_validator_alignment",
        ),
    )
    arguments = parser.parse_args(argv)
    install_network_deny()
    try:
        socket.getaddrinfo("example.invalid", 443)
    except NetworkDenied:
        pass
    else:
        raise NetworkDenied("DNS denial self-test did not fire")
    suite = unittest.defaultTestLoader.loadTestsFromNames(arguments.tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    print(f"R11A_NETWORK_DENY_VALID:{result.testsRun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
