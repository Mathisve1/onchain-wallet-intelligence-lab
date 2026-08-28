#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import os
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import difflib as _r11a_bytecode_boundary  # noqa: E402,F401
import unittest  # noqa: E402


class NetworkDenied(RuntimeError):
    pass


NETWORK_CLIENTS = frozenset(
    {
        "aws",
        "curl",
        "dig",
        "git-lfs",
        "git-remote-ftp",
        "git-remote-ftps",
        "git-remote-http",
        "git-remote-https",
        "git-shell",
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

_LOCAL_GIT_CONFIG = frozenset(
    {
        "core.fsmonitor=false",
        "core.hooksPath=/dev/null",
        "core.sparseCheckout=false",
        "core.sparseCheckoutCone=false",
        "core.untrackedCache=false",
    }
)


def _local_path(candidate: str, cwd: Path) -> Path:
    path = Path(candidate)
    if not path.is_absolute():
        path = cwd / path
    try:
        return path.resolve(strict=False)
    except OSError as exc:
        raise deny(f"ambiguous local Git path: {candidate!r}") from exc


def _require_local_git(
    command: Sequence[object] | str,
    *,
    cwd: object | None,
    environment: object | None,
) -> None:
    """Permit only the exact offline Git surface used by provenance tests.

    Git as a whole cannot be allowlisted: clone/fetch/pull/push/ls-remote and
    transport helpers can create network activity in a child process, beyond
    the Python socket monkeypatches.  This parser therefore recognizes a
    deliberately small set of local object/index/worktree operations and
    rejects every unrecognized global option, subcommand, and argument shape.
    """

    if isinstance(command, str) or not command:
        raise deny("string/empty Git subprocess command")
    try:
        argv = tuple(os.fspath(argument) for argument in command)
    except TypeError as exc:
        raise deny("non-path Git subprocess argument") from exc
    if not argv or os.path.basename(argv[0]).lower() != "git":
        raise deny("malformed Git subprocess command")
    if not all(isinstance(argument, str) and "\x00" not in argument for argument in argv):
        raise deny("non-string/NUL Git subprocess argument")

    try:
        local_cwd = Path(os.fspath(cwd)) if cwd is not None else Path.cwd()
        local_cwd = local_cwd.resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise deny("Git subprocess cwd is not a physical local directory") from exc
    if not local_cwd.is_dir():
        raise deny("Git subprocess cwd is not a local directory")

    offset = 1
    git_directory: Path | None = None
    work_tree: Path | None = None
    while offset < len(argv):
        argument = argv[offset]
        if argument == "--no-optional-locks":
            offset += 1
            continue
        if argument.startswith("--git-dir="):
            git_directory = _local_path(argument.partition("=")[2], local_cwd)
            offset += 1
            continue
        if argument.startswith("--work-tree="):
            work_tree = _local_path(argument.partition("=")[2], local_cwd)
            offset += 1
            continue
        if argument == "-c":
            if offset + 1 >= len(argv) or argv[offset + 1] not in _LOCAL_GIT_CONFIG:
                raise deny("unapproved Git configuration override")
            offset += 2
            continue
        break

    if git_directory is not None and git_directory != local_cwd / ".git":
        raise deny("Git metadata is not the cwd physical .git directory")
    if work_tree is not None and work_tree != local_cwd:
        raise deny("Git worktree escapes the cwd")
    if (git_directory is None) != (work_tree is None):
        raise deny("partial Git metadata/worktree binding")
    if offset >= len(argv):
        raise deny("missing local Git subcommand")

    subcommand = argv[offset]
    arguments = argv[offset + 1 :]
    allowed = False
    if subcommand == "init":
        allowed = arguments == ("-q",)
    elif subcommand == "config":
        config_read = (
            len(arguments) == 5
            and arguments[0].startswith("--file=")
            and _local_path(arguments[0].partition("=")[2], local_cwd)
            == local_cwd / ".git/config"
            and arguments[1:] == ("--no-includes", "--null", "--name-only", "--list")
        )
        config_write = arguments in {
            ("user.name", "R11A Offline Test"),
            ("user.email", "r11a-offline@example.invalid"),
            ("user.name", "R11A Snapshot Test"),
            ("user.email", "r11a-snapshot@example.invalid"),
        }
        allowed = config_read or config_write
    elif subcommand == "add":
        allowed = arguments in {
            ("--all",),
            ("--intent-to-add", "intent.txt"),
            ("governance/REPOSITORY_MANIFEST.sha256",),
        }
    elif subcommand == "commit":
        allowed = (
            len(arguments) == 3
            and arguments[:2] == ("-q", "-m")
            and arguments[2]
            in {
                "fixture",
                "self listed manifest",
                "tracked cache fixture",
                "unordered manifest",
                "wrong manifest digest",
            }
        )
        allowed = allowed or arguments == (
            "-q",
            "--allow-empty",
            "-m",
            "snapshot routing fixture",
        )
    elif subcommand == "update-index":
        cache_info = arguments[1].split(",") if len(arguments) == 2 else []
        allowed = (
            arguments in {
                ("--index-version=2",),
                ("--index-version=4",),
                ("--skip-worktree", "README.md"),
                ("--assume-unchanged", "README.md"),
            }
            or (
                len(arguments) == 2
                and arguments[0] == "--cacheinfo"
                and len(cache_info) == 3
                and cache_info[0] == "100644"
                and len(cache_info[1]) == 40
                and all(character in "0123456789abcdef" for character in cache_info[1])
                and cache_info[2] == "README.md"
            )
        )
    elif subcommand == "hash-object":
        allowed = arguments == ("-w", "--stdin")
    elif subcommand == "rev-parse":
        allowed = arguments in {
            ("--show-object-format",),
            ("--shared-index-path",),
            ("--verify", "HEAD^{commit}"),
            ("--verify", "HEAD^{tree}"),
            ("--verify", "HEAD"),
            ("--verify", "HEAD:README.md"),
            ("HEAD",),
        }
    elif subcommand == "ls-files":
        allowed = arguments in {
            ("--stage", "-z"),
            ("-t", "-z"),
            ("-v", "-z"),
            ("-f", "-z"),
            ("--debug", "-z"),
        }
    elif subcommand == "ls-tree":
        allowed = (
            (
                len(arguments) == 4
                and arguments[:3] == ("-r", "-z", "--full-tree")
            )
            or (
                len(arguments) == 5
                and arguments[:4] == ("-r", "-t", "-z", "--full-tree")
            )
        ) and (
            len(arguments[-1]) == 40
            and all(character in "0123456789abcdef" for character in arguments[-1])
        )
    elif subcommand == "cat-file":
        allowed = (
            arguments == ("--batch",)
            or (
                len(arguments) == 2
                and arguments[0] in {"blob", "commit"}
                and len(arguments[1]) == 40
                and all(character in "0123456789abcdef" for character in arguments[1])
            )
        )

    if not allowed:
        raise deny(f"Git subcommand/arguments not in local allowlist: {subcommand}")

    if git_directory is not None:
        if not git_directory.is_dir() or git_directory.is_symlink():
            raise deny("Git metadata is not a physical local directory")
        if not isinstance(environment, Mapping):
            raise deny("authenticated Git plumbing environment is absent")
        if environment.get("GIT_NO_LAZY_FETCH") != "1":
            raise deny("authenticated Git plumbing did not disable lazy fetch")
        if environment.get("GIT_NO_REPLACE_OBJECTS") != "1":
            raise deny("authenticated Git plumbing did not disable replacement objects")


def deny(label: str) -> NetworkDenied:
    return NetworkDenied(f"R11A network-deny harness blocked: {label}")


def _audit(event: str, arguments: tuple[object, ...]) -> None:
    if event.startswith("socket."):
        raise deny(event)
    if event == "subprocess.Popen" and arguments:
        executable = os.path.basename(os.fsdecode(arguments[0])).lower()
        if executable == "git":
            command = arguments[1] if len(arguments) > 1 else (arguments[0],)
            cwd = arguments[2] if len(arguments) > 2 else None
            environment = arguments[3] if len(arguments) > 3 else None
            _require_local_git(command, cwd=cwd, environment=environment)
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
        first = args.split()[0] if isinstance(args, str) else os.fsdecode(args[0])
        executable = os.path.basename(first).lower()
        if executable == "git":
            if popen_kwargs.get("shell"):
                raise deny("shell-mediated Git subprocess")
            _require_local_git(
                args,
                cwd=popen_kwargs.get("cwd"),
                environment=popen_kwargs.get("env"),
            )
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
            "tests.test_archive_inventory_r11a_github_review_evidence",
            "tests.test_archive_inventory_r11a_review_stage_chain",
            "tests.test_archive_inventory_r11a_repository_provenance",
            "tests.test_r11a_workflow_identity",
            "tests.test_archive_inventory_r11a_execution_artifact_hardening",
            "tests.test_archive_inventory_r11a_runtime_binding_review",
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
    try:
        subprocess.run(
            ["git", "fetch", "https://example.invalid/repository.git"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except NetworkDenied:
        pass
    else:
        raise NetworkDenied("network-capable Git denial self-test did not fire")
    suite = unittest.defaultTestLoader.loadTestsFromNames(arguments.tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    print(f"R11A_NETWORK_DENY_VALID:{result.testsRun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
