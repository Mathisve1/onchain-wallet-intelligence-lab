#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import unicodedata
import ctypes
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator, Mapping


MANIFEST_PATH = "governance/REPOSITORY_MANIFEST.sha256"
_OID = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_INDEX_DEBUG_METADATA = re.compile(
    rb"  ctime: [0-9]+:[0-9]+\n"
    rb"  mtime: [0-9]+:[0-9]+\n"
    rb"  dev: [0-9]+\tino: [0-9]+\n"
    rb"  uid: [0-9]+\tgid: [0-9]+\n"
    rb"  size: [0-9]+\tflags: ([0-9a-f]+)\n\Z"
)
_SUPPORTED_INDEX_VERSIONS = frozenset({2})
_PROHIBITED_GIT_REDIRECTIONS = (
    "commondir",
    "objects/info/alternates",
    "objects/info/http-alternates",
    "index.lock",
    "modules",
    "worktrees",
)
_PROHIBITED_CONFIG_KEYS = frozenset(
    {
        "core.fsmonitor",
        "core.hookspath",
        "core.sparsecheckout",
        "core.sparsecheckoutcone",
        "core.splitindex",
        "core.worktree",
        "extensions.partialclone",
        "extensions.worktreeconfig",
    }
)
_R11A_REPOSITORY = "Mathisve1/onchain-wallet-intelligence-lab"
_R11A_WORKFLOW_NAME = "Hyperliquid Archive R11A Identity Boundary Diagnostic"
_R11A_WORKFLOW_FILE = "hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
_R11A_MAIN_REF = "refs/heads/main"
_HISTORICAL_R11A_IMPLEMENTATION_TEST = (
    "tests/test_archive_inventory_r11a_implementation.py"
)
_HISTORICAL_R11A_IMPLEMENTATION_TEST_SHA256 = (
    "0961a693c37cf21b2ce840840eea6d9b0de2945518f3e8feee350bb6bdd2642c"
)


class RepositoryProvenanceError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RepositoryProvenanceError(message)


@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    mode: int
    oid: str
    sha256: str
    raw: bytes


@dataclass(frozen=True)
class AuthenticatedRepositorySnapshot:
    _source_root: Path
    head: str
    tree: str
    index_version: int
    entries: tuple[SnapshotEntry, ...]
    _index_raw: bytes
    _source_identity: tuple[tuple[str, int, int], ...]
    _git_identity: tuple[int, int]
    _worktree_identity: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class AuthenticatedRepository:
    """Context-bound immutable semantic repository input.

    Deliberately exposes no mutable source-root path.  Security consumers get
    only the authenticated materialized root for the lifetime of the context.
    """

    snapshot_root: Path
    head: str
    tree: str
    index_version: int
    entries: tuple[SnapshotEntry, ...]
    _source_root: Path
    _watcher: "_SnapshotWatcher | None" = field(
        default=None,
        repr=False,
        compare=False,
    )


class _SnapshotWatcher:
    """Linux inotify proof that snapshot bytes were stable for every consumer."""

    _MASK = (
        0x00000002  # IN_MODIFY
        | 0x00000004  # IN_ATTRIB
        | 0x00000008  # IN_CLOSE_WRITE
        | 0x00000100  # IN_CREATE
        | 0x00000200  # IN_DELETE
        | 0x00000040  # IN_MOVED_FROM
        | 0x00000080  # IN_MOVED_TO
        | 0x00000400  # IN_DELETE_SELF
        | 0x00000800  # IN_MOVE_SELF
    )

    def __init__(self, descriptor: int) -> None:
        self._descriptor = descriptor

    @classmethod
    def start(cls, root: Path) -> "_SnapshotWatcher":
        library = ctypes.CDLL(None, use_errno=True)
        initialize = getattr(library, "inotify_init1", None)
        add_watch = getattr(library, "inotify_add_watch", None)
        _require(
            initialize is not None and add_watch is not None,
            "authenticated snapshot requires Linux inotify",
        )
        initialize.argtypes = [ctypes.c_int]
        initialize.restype = ctypes.c_int
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        descriptor = initialize(os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
        if descriptor < 0:
            error = ctypes.get_errno()
            raise RepositoryProvenanceError(
                f"cannot initialize authenticated snapshot watcher: errno {error}"
            )
        try:
            stack = [root]
            while stack:
                directory = stack.pop()
                information = directory.lstat()
                _require(
                    stat.S_ISDIR(information.st_mode)
                    and not stat.S_ISLNK(information.st_mode),
                    "snapshot watcher encountered non-physical directory",
                )
                watch = add_watch(
                    descriptor,
                    os.fsencode(directory),
                    cls._MASK,
                )
                if watch < 0:
                    error = ctypes.get_errno()
                    raise RepositoryProvenanceError(
                        f"cannot watch authenticated snapshot directory: errno {error}"
                    )
                for child in os.scandir(directory):
                    child_information = child.stat(follow_symlinks=False)
                    if stat.S_ISDIR(child_information.st_mode):
                        _require(
                            not stat.S_ISLNK(child_information.st_mode),
                            "snapshot watcher encountered symlink directory",
                        )
                        stack.append(Path(child.path))
                        continue
                    _require(
                        stat.S_ISREG(child_information.st_mode)
                        and not stat.S_ISLNK(child_information.st_mode)
                        and child_information.st_nlink == 1,
                        "snapshot watcher encountered non-private file",
                    )
                    file_watch = add_watch(
                        descriptor,
                        os.fsencode(child.path),
                        cls._MASK,
                    )
                    if file_watch < 0:
                        error = ctypes.get_errno()
                        raise RepositoryProvenanceError(
                            f"cannot watch authenticated snapshot file: errno {error}"
                        )
            watcher = cls(descriptor)
            watcher.require_clean("watcher initialization")
            return watcher
        except BaseException:
            os.close(descriptor)
            raise

    def require_clean(self, label: str) -> None:
        observed = bytearray()
        while True:
            try:
                chunk = os.read(self._descriptor, 64 * 1024)
            except BlockingIOError:
                break
            except OSError as exc:
                raise RepositoryProvenanceError(
                    f"authenticated snapshot watcher failed {label}"
                ) from exc
            if not chunk:
                break
            observed.extend(chunk)
        _require(
            not observed,
            f"authenticated snapshot changed {label}",
        )

    def close(self) -> None:
        if self._descriptor >= 0:
            os.close(self._descriptor)
            self._descriptor = -1


@dataclass(frozen=True)
class _CacheTreeNode:
    path: str
    entry_count: int
    oid: str
    children: tuple["_CacheTreeNode", ...]


@dataclass(frozen=True)
class _ParsedGitIndex:
    version: int
    entries: tuple["_GitEntry", ...]
    cache_tree: _CacheTreeNode | None


@dataclass(frozen=True)
class _GitEntry:
    path: str
    mode: int
    oid: str


def _checked_directory(path: Path, label: str) -> Path:
    lexical = Path(path)
    _require(lexical.is_absolute(), f"{label} must be an absolute lexical path")
    _require(lexical.anchor == os.sep, f"{label} anchor is ambiguous")
    _require(".." not in lexical.parts, f"{label} contains traversal")
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        try:
            information = current.lstat()
        except OSError as exc:
            raise RepositoryProvenanceError(
                f"{label} path component is absent: {current}"
            ) from exc
        _require(
            not stat.S_ISLNK(information.st_mode),
            f"{label} path component is symlink: {current}",
        )
        _require(
            stat.S_ISDIR(information.st_mode),
            f"{label} path component is not directory: {current}",
        )
    return lexical


def _directory_chain_identity(path: Path) -> tuple[tuple[str, int, int], ...]:
    lexical = _checked_directory(path, "repository root")
    current = Path(lexical.anchor)
    result: list[tuple[str, int, int]] = []
    for part in lexical.parts[1:]:
        current /= part
        information = current.lstat()
        result.append((str(current), information.st_dev, information.st_ino))
    return tuple(result)


def _provenance_checkpoint(
    label: str,
    *,
    source_root: Path,
    snapshot_root: Path | None = None,
) -> None:
    """Private deterministic race-test seam; production intentionally does nothing."""

    del label, source_root, snapshot_root


def _normalized_collision_key(relative: str) -> str:
    return unicodedata.normalize("NFKC", relative).casefold()


def _validate_relative_path(
    raw: bytes | str,
    *,
    collision_map: dict[str, str] | None = None,
) -> str:
    if isinstance(raw, bytes):
        try:
            relative = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("repository path is not strict UTF-8") from exc
        _require(relative.encode("utf-8") == raw, "repository path UTF-8 is non-canonical")
    else:
        _require(type(raw) is str, "repository path must be bytes or string")
        relative = raw

    _require(relative != "", "empty repository path prohibited")
    _require("\x00" not in relative, f"NUL repository path prohibited: {relative!r}")
    _require("\\" not in relative, f"backslash repository path prohibited: {relative!r}")
    pure = PurePosixPath(relative)
    _require(not pure.is_absolute(), f"absolute repository path prohibited: {relative!r}")
    _require(
        pure.as_posix() == relative,
        f"non-canonical repository path prohibited: {relative!r}",
    )
    _require(
        bool(pure.parts) and all(part not in {"", ".", ".."} for part in pure.parts),
        f"unsafe repository path component: {relative!r}",
    )
    _require(
        unicodedata.normalize("NFC", relative) == relative,
        f"non-NFC repository path prohibited: {relative!r}",
    )
    for part in pure.parts:
        _require(part == part.strip(), f"repository path whitespace ambiguity: {relative!r}")
        _require(
            not any(unicodedata.category(character).startswith("C") for character in part),
            f"repository path control character prohibited: {relative!r}",
        )
        _require(
            _normalized_collision_key(part) != ".git",
            f"repository metadata path component prohibited: {relative!r}",
        )

    if collision_map is not None:
        key = _normalized_collision_key(relative)
        previous = collision_map.get(key)
        _require(
            previous in {None, relative},
            f"repository path normalization/case collision: {previous!r} and {relative!r}",
        )
        collision_map[key] = relative
    return relative


def _parse_canonical_decimal(raw: bytes, label: str) -> int:
    _require(
        raw == b"0"
        or (
            raw[:1] in b"123456789"
            and (len(raw) == 1 or raw[1:].isdigit())
        ),
        f"{label} is not canonical non-negative decimal",
    )
    try:
        value = int(raw.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RepositoryProvenanceError(f"{label} is malformed") from exc
    _require(value <= 0x7FFFFFFF, f"{label} exceeds supported range")
    return value


def _parse_cache_tree_payload(payload: bytes) -> _CacheTreeNode:
    """Parse one complete Git cache-tree extension without trusting Git."""

    node_budget = max(1, len(payload) // 24)
    observed: set[str] = set()
    collisions: dict[str, str] = {}

    def parse_node(position: int, parent: str | None) -> tuple[_CacheTreeNode, int]:
        nonlocal node_budget
        _require(node_budget > 0, "Git TREE node count exceeds payload bound")
        node_budget -= 1
        nul = payload.find(b"\0", position)
        _require(nul >= position, "Git TREE path is not NUL terminated")
        raw_component = payload[position:nul]
        if parent is None:
            _require(raw_component == b"", "Git TREE root path is not empty")
            path = ""
        else:
            _require(raw_component != b"", "Git TREE child path is empty")
            component = _validate_relative_path(raw_component)
            _require("/" not in component, "Git TREE child path is not one component")
            path = component if parent == "" else f"{parent}/{component}"
            _validate_relative_path(path, collision_map=collisions)
        _require(path not in observed, f"duplicate Git TREE path: {path or '.'}")
        observed.add(path)

        header_start = nul + 1
        newline = payload.find(b"\n", header_start)
        _require(newline >= header_start, "Git TREE count header is truncated")
        header = payload[header_start:newline]
        raw_entries, separator, raw_subtrees = header.partition(b" ")
        _require(
            separator == b" " and raw_entries != b"" and raw_subtrees != b"" and b" " not in raw_subtrees,
            "Git TREE count header is malformed",
        )
        entry_count = _parse_canonical_decimal(raw_entries, "Git TREE entry count")
        subtree_count = _parse_canonical_decimal(raw_subtrees, "Git TREE subtree count")
        _require(subtree_count <= node_budget, "Git TREE subtree count exceeds payload bound")

        oid_start = newline + 1
        oid_end = oid_start + 20
        _require(oid_end <= len(payload), "Git TREE OID is truncated")
        oid = payload[oid_start:oid_end].hex()
        _require(_OID.fullmatch(oid) is not None and oid != "0" * 40, "Git TREE OID is invalid")

        children: list[_CacheTreeNode] = []
        position = oid_end
        child_keys: dict[str, str] = {}
        for _ in range(subtree_count):
            child, position = parse_node(position, path)
            component = PurePosixPath(child.path).name
            collision = _normalized_collision_key(component)
            previous = child_keys.get(collision)
            _require(previous is None, f"Git TREE child collision: {previous!r} and {component!r}")
            child_keys[collision] = component
            children.append(child)
        return _CacheTreeNode(path, entry_count, oid, tuple(children)), position

    root, end = parse_node(0, None)
    _require(end == len(payload), "Git TREE payload has trailing or excess bytes")
    return root


def _parse_git_index(raw: bytes) -> _ParsedGitIndex:
    """Strictly parse the complete supported Git index through its checksum."""

    _require(len(raw) >= 32 and raw[:4] == b"DIRC", "malformed Git index header")
    version, entry_count = struct.unpack(">II", raw[4:12])
    _require(version in _SUPPORTED_INDEX_VERSIONS, f"unsupported Git index version: {version}")
    checksum_offset = len(raw) - 20
    _require(checksum_offset >= 12, "malformed Git index checksum boundary")
    _require(
        hashlib.sha1(raw[:checksum_offset]).digest() == raw[checksum_offset:],
        "Git index checksum mismatch",
    )

    entries: list[_GitEntry] = []
    collisions: dict[str, str] = {}
    observed: set[str] = set()
    previous_raw_path: bytes | None = None
    position = 12
    for _ in range(entry_count):
        entry_start = position
        fixed_end = entry_start + 62
        _require(fixed_end <= checksum_offset, "truncated Git index entry header")
        mode = struct.unpack(">I", raw[entry_start + 24 : entry_start + 28])[0]
        oid_raw = raw[entry_start + 40 : entry_start + 60]
        flags = struct.unpack(">H", raw[entry_start + 60 : fixed_end])[0]
        _require(flags & 0x8000 == 0, "assume-valid Git index state prohibited")
        _require(flags & 0x4000 == 0, "extended Git index flags prohibited")
        _require(flags & 0x3000 == 0, "unmerged Git index stage prohibited")
        _require(mode in {0o100644, 0o100755}, "tracked symlink/submodule/mode prohibited")
        _require(oid_raw != b"\0" * 20, "zero Git index OID prohibited")

        nul = raw.find(b"\0", fixed_end, checksum_offset)
        _require(nul >= fixed_end, "Git index pathname is not NUL terminated")
        raw_path = raw[fixed_end:nul]
        name_length = flags & 0x0FFF
        _require(
            name_length == len(raw_path) if len(raw_path) < 0x0FFF else name_length == 0x0FFF,
            "Git index pathname length flag drift",
        )
        relative = _validate_relative_path(raw_path, collision_map=collisions)
        _require(relative not in observed, f"duplicate Git index path: {relative}")
        _require(not _is_cache_like_path(relative), f"tracked Python cache/bytecode prohibited: {relative}")
        _require(
            previous_raw_path is None or previous_raw_path < raw_path,
            "Git index paths are not strictly byte ordered",
        )
        previous_raw_path = raw_path
        observed.add(relative)

        consumed = nul + 1 - entry_start
        position = entry_start + ((consumed + 7) // 8) * 8
        _require(position <= checksum_offset, "Git index entry padding crosses checksum")
        _require(
            raw[nul:position] == b"\0" * (position - nul),
            f"Git index entry padding is nonzero: {relative}",
        )
        entries.append(_GitEntry(relative, mode, oid_raw.hex()))

    cache_tree: _CacheTreeNode | None = None
    signatures: set[bytes] = set()
    while position < checksum_offset:
        _require(position + 8 <= checksum_offset, "truncated Git index extension header")
        signature = raw[position : position + 4]
        size = struct.unpack(">I", raw[position + 4 : position + 8])[0]
        _require(signature not in signatures, "duplicate Git index extension")
        signatures.add(signature)
        payload_start = position + 8
        payload_end = payload_start + size
        _require(
            payload_end <= checksum_offset,
            "Git index extension payload crosses checksum boundary",
        )
        payload = raw[payload_start:payload_end]
        if signature == b"TREE":
            _require(cache_tree is None, "duplicate Git TREE extension")
            cache_tree = _parse_cache_tree_payload(payload)
        else:
            try:
                rendered = signature.decode("ascii")
            except UnicodeDecodeError:
                rendered = signature.hex()
            raise RepositoryProvenanceError(
                f"unsupported Git index extension: {rendered}"
            )
        position = payload_end
    _require(position == checksum_offset, "Git index has hidden trailing bytes")
    _require(len(entries) == entry_count, "Git index entry count drift")
    return _ParsedGitIndex(version, tuple(entries), cache_tree)


def _is_cache_like_path(relative: str) -> bool:
    normalized_parts = tuple(
        _normalized_collision_key(part).rstrip()
        for part in PurePosixPath(relative).parts
    )
    normalized_name = normalized_parts[-1]
    return "__pycache__" in normalized_parts or normalized_name.endswith((".pyc", ".pyo"))


def _read_regular_file(path: Path, label: str, *, one_link: bool = True) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RepositoryProvenanceError(f"cannot open {label}: {path}") from exc
    try:
        before = os.fstat(descriptor)
        _require(stat.S_ISREG(before.st_mode), f"{label} is not regular: {path}")
        if one_link:
            _require(before.st_nlink == 1, f"{label} has hard-link alias: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    _require(identity_before == identity_after, f"{label} changed while read: {path}")
    raw = b"".join(chunks)
    _require(len(raw) == before.st_size, f"{label} size changed while read: {path}")
    return raw, before


def _git_environment() -> dict[str, str]:
    # Git plumbing is part of the provenance boundary.  Do not inherit PATH,
    # dynamic-loader, locale, pager, credential-helper, or repository-control
    # variables from the caller.  The fixed system search path is sufficient
    # for the small built-in, offline plumbing command set below.
    return {
        "PATH": os.defpath,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
    }


def _git_command(root: Path, *arguments: str) -> list[str]:
    return [
        "git",
        "--no-optional-locks",
        f"--git-dir={root / '.git'}",
        f"--work-tree={root}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.sparseCheckout=false",
        "-c",
        "core.sparseCheckoutCone=false",
        "-c",
        "core.untrackedCache=false",
        *arguments,
    ]


def _git(root: Path, *arguments: str, input_data: bytes | None = None) -> bytes:
    try:
        completed = subprocess.run(
            _git_command(root, *arguments),
            cwd=root,
            env=_git_environment(),
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryProvenanceError(f"Git plumbing failed to start: {' '.join(arguments)}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[:500]
        raise RepositoryProvenanceError(
            f"Git plumbing failed ({' '.join(arguments)}): {detail}"
        )
    _require(
        completed.stderr == b"",
        "unexpected Git plumbing diagnostic "
        f"({' '.join(arguments)}): "
        + completed.stderr.decode("utf-8", errors="replace").strip()[:500],
    )
    return completed.stdout


def _validate_git_metadata(root: Path) -> tuple[Path, bytes, _ParsedGitIndex]:
    git_directory = root / ".git"
    try:
        git_information = git_directory.lstat()
    except OSError as exc:
        raise RepositoryProvenanceError("physical .git directory is absent") from exc
    _require(not stat.S_ISLNK(git_information.st_mode), "physical .git directory is symlink")
    _require(
        stat.S_ISDIR(git_information.st_mode),
        "gitfile indirection or non-directory .git is prohibited",
    )

    stack = [git_directory]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name.encode("utf-8"))
        except (OSError, UnicodeError) as exc:
            raise RepositoryProvenanceError(f"cannot scan Git metadata: {directory}") from exc
        for entry in entries:
            try:
                information = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise RepositoryProvenanceError(f"cannot lstat Git metadata: {entry.path}") from exc
            _require(
                not stat.S_ISLNK(information.st_mode),
                f"symlinked Git metadata prohibited: {entry.path}",
            )
            if stat.S_ISDIR(information.st_mode):
                stack.append(Path(entry.path))
                continue
            _require(
                stat.S_ISREG(information.st_mode),
                f"special Git metadata prohibited: {entry.path}",
            )
            _require(
                information.st_nlink == 1,
                f"hard-linked Git metadata prohibited: {entry.path}",
            )

    for relative in _PROHIBITED_GIT_REDIRECTIONS:
        _require(
            not (git_directory / PurePosixPath(relative)).exists(),
            f"Git metadata redirection/state prohibited: .git/{relative}",
        )
    _require(
        not any(git_directory.glob("sharedindex.*")),
        "split Git index metadata prohibited",
    )

    index_raw, _ = _read_regular_file(git_directory / "index", "Git index")
    parsed_index = _parse_git_index(index_raw)

    config = git_directory / "config"
    _read_regular_file(config, "Git configuration")
    config_names = _git(
        root,
        "config",
        f"--file={config}",
        "--no-includes",
        "--null",
        "--name-only",
        "--list",
    )
    for raw_name in _nul_records(config_names, "Git configuration key inventory"):
        try:
            name = raw_name.decode("utf-8").casefold()
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("Git configuration key is not UTF-8") from exc
        _require(
            not name.startswith(("include.", "includeif.")),
            f"external Git configuration include prohibited: {name}",
        )
        _require(name not in _PROHIBITED_CONFIG_KEYS, f"unsafe Git configuration prohibited: {name}")
        _require(
            not (name.startswith("remote.") and name.endswith(".promisor")),
            f"partial-clone promisor configuration prohibited: {name}",
        )
    return git_directory, index_raw, parsed_index


def _nul_records(raw: bytes, label: str) -> tuple[bytes, ...]:
    if not raw:
        return ()
    _require(raw.endswith(b"\0"), f"{label} is not NUL terminated")
    records = tuple(raw[:-1].split(b"\0"))
    _require(all(record != b"" for record in records), f"{label} contains empty record")
    return records


def _parse_index_entries(raw: bytes, expected_count: int) -> tuple[_GitEntry, ...]:
    collisions: dict[str, str] = {}
    result: list[_GitEntry] = []
    observed: set[str] = set()
    for record in _nul_records(raw, "Git index inventory"):
        header, separator, raw_path = record.partition(b"\t")
        _require(separator == b"\t", "malformed Git index inventory row")
        fields = header.split(b" ")
        _require(len(fields) == 3, "malformed Git index inventory header")
        raw_mode, raw_oid, raw_stage = fields
        _require(raw_mode in {b"100644", b"100755"}, "tracked symlink/submodule/mode prohibited")
        try:
            oid = raw_oid.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("non-ASCII Git index OID") from exc
        _require(_OID.fullmatch(oid) is not None and oid != "0" * 40, "invalid/zero Git index OID")
        _require(raw_stage == b"0", "unmerged Git index stage prohibited")
        relative = _validate_relative_path(raw_path, collision_map=collisions)
        _require(relative not in observed, f"duplicate Git index path: {relative}")
        _require(not _is_cache_like_path(relative), f"tracked Python cache/bytecode prohibited: {relative}")
        observed.add(relative)
        result.append(_GitEntry(relative, int(raw_mode, 8), oid))
    _require(len(result) == expected_count, "Git index header entry count drift")
    return tuple(result)


def _parse_tagged_paths(raw: bytes, label: str) -> tuple[str, ...]:
    collisions: dict[str, str] = {}
    result: list[str] = []
    for record in _nul_records(raw, label):
        _require(record.startswith(b"H "), f"{label} contains prohibited index state")
        result.append(_validate_relative_path(record[2:], collision_map=collisions))
    _require(len(result) == len(set(result)), f"{label} contains duplicate path")
    return tuple(result)


def _require_zero_index_debug_flags(raw: bytes, paths: tuple[str, ...]) -> None:
    position = 0
    encoded_paths = tuple(path.encode("utf-8") for path in paths)
    for offset, encoded_path in enumerate(encoded_paths):
        prefix = encoded_path + b"\0"
        _require(
            raw.startswith(prefix, position),
            "Git index debug inventory path/order drift",
        )
        metadata_start = position + len(prefix)
        if offset + 1 < len(encoded_paths):
            next_marker = b"\n" + encoded_paths[offset + 1] + b"\0"
            boundary = raw.find(next_marker, metadata_start)
            _require(boundary >= 0, "truncated Git index debug inventory")
            metadata = raw[metadata_start : boundary + 1]
            position = boundary + 1
        else:
            metadata = raw[metadata_start:]
            position = len(raw)
        match = _INDEX_DEBUG_METADATA.fullmatch(metadata)
        _require(match is not None, "malformed Git index debug metadata")
        _require(
            match.group(1) == b"0",
            f"unsupported Git index flags for {paths[offset]}",
        )
    _require(position == len(raw), "unexpected trailing Git index debug output")


def _parse_tree_entries(raw: bytes) -> tuple[_GitEntry, ...]:
    collisions: dict[str, str] = {}
    result: list[_GitEntry] = []
    observed: set[str] = set()
    for record in _nul_records(raw, "Git tree inventory"):
        header, separator, raw_path = record.partition(b"\t")
        _require(separator == b"\t", "malformed Git tree inventory row")
        fields = header.split(b" ")
        _require(len(fields) == 3, "malformed Git tree inventory header")
        raw_mode, object_type, raw_oid = fields
        _require(
            raw_mode in {b"100644", b"100755"} and object_type == b"blob",
            "tree symlink/submodule/non-blob prohibited",
        )
        try:
            oid = raw_oid.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("non-ASCII Git tree OID") from exc
        _require(_OID.fullmatch(oid) is not None, "invalid Git tree OID")
        relative = _validate_relative_path(raw_path, collision_map=collisions)
        _require(relative not in observed, f"duplicate Git tree path: {relative}")
        _require(not _is_cache_like_path(relative), f"tracked Python cache/bytecode prohibited: {relative}")
        observed.add(relative)
        result.append(_GitEntry(relative, int(raw_mode, 8), oid))
    return tuple(result)


def _read_git_objects(
    root: Path,
    expected_types: Mapping[str, bytes],
) -> dict[str, bytes]:
    requested = tuple(sorted(expected_types))
    output = _git(
        root,
        "cat-file",
        "--batch",
        input_data=b"".join(oid.encode("ascii") + b"\n" for oid in requested),
    )
    position = 0
    result: dict[str, bytes] = {}
    for expected_oid in requested:
        newline = output.find(b"\n", position)
        _require(newline >= 0, "truncated git cat-file header")
        header = output[position:newline].split(b" ")
        _require(len(header) == 3, "missing or malformed Git blob object")
        raw_oid, object_type, raw_size = header
        try:
            observed_oid = raw_oid.decode("ascii")
            size = int(raw_size.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RepositoryProvenanceError("malformed Git blob header") from exc
        _require(
            observed_oid == expected_oid
            and object_type == expected_types[expected_oid],
            "Git object identity/type drift",
        )
        position = newline + 1
        end = position + size
        _require(
            end < len(output) and output[end : end + 1] == b"\n",
            "truncated Git object bytes",
        )
        result[expected_oid] = output[position:end]
        expected_object_hash = hashlib.sha1(
            object_type
            + b" "
            + str(size).encode("ascii")
            + b"\0"
            + result[expected_oid]
        ).hexdigest()
        _require(
            expected_object_hash == expected_oid,
            f"Git object hash mismatch: {expected_oid}",
        )
        position = end + 1
    _require(position == len(output), "unexpected trailing git cat-file output")
    return result


def _read_git_blobs(root: Path, oids: Iterable[str]) -> dict[str, bytes]:
    return _read_git_objects(root, {oid: b"blob" for oid in oids})


def _parse_complete_tree_inventory(
    raw: bytes,
) -> tuple[tuple[_GitEntry, ...], dict[str, str]]:
    collisions: dict[str, str] = {}
    leaves: list[_GitEntry] = []
    trees: dict[str, str] = {}
    observed: set[str] = set()
    for record in _nul_records(raw, "complete Git tree inventory"):
        header, separator, raw_path = record.partition(b"\t")
        _require(separator == b"\t", "malformed complete Git tree inventory row")
        fields = header.split(b" ")
        _require(len(fields) == 3, "malformed complete Git tree inventory header")
        raw_mode, object_type, raw_oid = fields
        try:
            oid = raw_oid.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("non-ASCII complete tree OID") from exc
        _require(_OID.fullmatch(oid) is not None, "invalid complete tree OID")
        relative = _validate_relative_path(raw_path, collision_map=collisions)
        _require(relative not in observed, f"duplicate complete tree path: {relative}")
        observed.add(relative)
        if object_type == b"tree":
            _require(raw_mode == b"040000", "non-canonical Git tree mode")
            trees[relative] = oid
            continue
        _require(
            object_type == b"blob" and raw_mode in {b"100644", b"100755"},
            "tree symlink/submodule/non-blob prohibited",
        )
        _require(
            not _is_cache_like_path(relative),
            f"tracked Python cache/bytecode prohibited: {relative}",
        )
        leaves.append(_GitEntry(relative, int(raw_mode, 8), oid))
    return tuple(leaves), trees


def _validate_cache_tree_semantics(
    cache_tree: _CacheTreeNode | None,
    *,
    root_tree: str,
    descendant_trees: Mapping[str, str],
    entries: tuple[_GitEntry, ...],
) -> None:
    if cache_tree is None:
        return

    expected_oids = {"": root_tree, **descendant_trees}
    expected_children: dict[str, set[str]] = {path: set() for path in expected_oids}
    for path in descendant_trees:
        parent = PurePosixPath(path).parent.as_posix()
        if parent == ".":
            parent = ""
        _require(parent in expected_children, f"Git tree parent is absent: {path}")
        expected_children[parent].add(path)

    expected_counts: dict[str, int] = {}
    for path in expected_oids:
        prefix = "" if path == "" else f"{path}/"
        expected_counts[path] = sum(
            entry.path.startswith(prefix) for entry in entries
        )

    observed: dict[str, _CacheTreeNode] = {}

    def visit(node: _CacheTreeNode) -> None:
        _require(node.path not in observed, f"duplicate semantic Git TREE path: {node.path or '.'}")
        observed[node.path] = node
        for child in node.children:
            visit(child)

    visit(cache_tree)
    _require(set(observed) == set(expected_oids), "Git TREE path inventory differs from exact HEAD")
    for path, node in observed.items():
        _require(node.oid == expected_oids[path], f"Git TREE OID differs from exact HEAD: {path or '.'}")
        _require(
            node.entry_count == expected_counts[path],
            f"Git TREE entry count differs from exact HEAD: {path or '.'}",
        )
        _require(
            {child.path for child in node.children} == expected_children[path],
            f"Git TREE child inventory differs from exact HEAD: {path or '.'}",
        )


def _validate_manifest(entries: Mapping[str, _GitEntry], blobs: Mapping[str, bytes]) -> None:
    _require(MANIFEST_PATH in entries, "repository manifest is not tracked")
    manifest_raw = blobs[entries[MANIFEST_PATH].oid]
    _require(manifest_raw.endswith(b"\n") and not manifest_raw.endswith(b"\n\n"), "manifest LF framing drift")
    rows = manifest_raw[:-1].split(b"\n")
    observed: dict[str, str] = {}
    observed_order: list[bytes] = []
    collisions: dict[str, str] = {}
    for row in rows:
        digest_raw, separator, path_raw = row.partition(b"  ")
        _require(separator == b"  " and path_raw != b"", "malformed repository manifest row")
        try:
            digest = digest_raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RepositoryProvenanceError("manifest digest is not ASCII") from exc
        _require(_DIGEST.fullmatch(digest) is not None, "manifest digest format drift")
        relative = _validate_relative_path(path_raw, collision_map=collisions)
        _require(relative not in observed, f"duplicate manifest path: {relative}")
        observed[relative] = digest
        observed_order.append(path_raw)
    _require(observed_order == sorted(observed_order), "manifest paths are not UTF-8 byte ordered")
    expected_paths = set(entries) - {MANIFEST_PATH}
    _require(set(observed) == expected_paths, "repository manifest path coverage drift")
    for relative, digest in observed.items():
        _require(
            hashlib.sha256(blobs[entries[relative].oid]).hexdigest() == digest,
            f"repository manifest digest drift: {relative}",
        )


def _scan_and_bind_worktree(
    root: Path,
    entries: Mapping[str, _GitEntry],
    blobs: Mapping[str, bytes],
) -> tuple[tuple[object, ...], ...]:
    files: dict[str, tuple[Path, os.stat_result]] = {}
    directories: dict[str, os.stat_result] = {"": root.lstat()}
    stack: list[tuple[Path, PurePosixPath | None]] = [(root, None)]
    collisions: dict[str, str] = {}
    while stack:
        directory, prefix = stack.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name.encode("utf-8"), reverse=True)
        except (OSError, UnicodeError) as exc:
            raise RepositoryProvenanceError(f"cannot scan repository worktree: {directory}") from exc
        for child in children:
            try:
                information = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise RepositoryProvenanceError(f"cannot lstat worktree entry: {child.path}") from exc
            if prefix is None and child.name == ".git":
                _require(stat.S_ISDIR(information.st_mode) and not stat.S_ISLNK(information.st_mode), "physical .git changed during scan")
                continue
            relative_path = PurePosixPath(child.name) if prefix is None else prefix / child.name
            relative = _validate_relative_path(relative_path.as_posix(), collision_map=collisions)
            _require(not stat.S_ISLNK(information.st_mode), f"worktree symlink prohibited: {relative}")
            if stat.S_ISDIR(information.st_mode):
                directories[relative] = information
                stack.append((Path(child.path), relative_path))
                continue
            _require(stat.S_ISREG(information.st_mode), f"worktree special file prohibited: {relative}")
            _require(information.st_nlink == 1, f"worktree hard-link prohibited: {relative}")
            files[relative] = (Path(child.path), information)

    tracked_paths = set(entries)
    missing = tracked_paths - set(files)
    _require(not missing, "tracked worktree path absent: " + ", ".join(sorted(missing)[:5]))

    for relative, entry in entries.items():
        path, scanned = files[relative]
        raw, information = _read_regular_file(path, "tracked worktree file")
        _require(
            (scanned.st_dev, scanned.st_ino) == (information.st_dev, information.st_ino),
            f"tracked worktree file replaced during scan: {relative}",
        )
        _require(raw == blobs[entry.oid], f"working-tree byte drift: {relative}")
        expected_executable = entry.mode == 0o100755
        _require(
            bool(information.st_mode & 0o111) == expected_executable,
            f"working-tree executable mode drift: {relative}",
        )

    untracked = sorted(set(files) - tracked_paths, key=lambda value: value.encode("utf-8"))
    _require(
        not untracked,
        "untracked repository file prohibited: " + ", ".join(untracked[:5]),
    )

    expected_directories: set[str] = set()
    for relative in tracked_paths:
        for parent in PurePosixPath(relative).parents:
            parent_string = parent.as_posix()
            if parent_string != ".":
                expected_directories.add(parent_string)
    _require(
        set(directories) - {""} == expected_directories,
        "untracked/empty repository directory prohibited",
    )
    identity: list[tuple[object, ...]] = []
    for relative, information in directories.items():
        identity.append(
            (
                "directory",
                relative,
                information.st_dev,
                information.st_ino,
                stat.S_IMODE(information.st_mode),
            )
        )
    for relative, (path, scanned) in files.items():
        information = path.lstat()
        _require(
            (information.st_dev, information.st_ino)
            == (scanned.st_dev, scanned.st_ino),
            f"worktree file replaced after byte reconciliation: {relative}",
        )
        identity.append(
            (
                "file",
                relative,
                information.st_dev,
                information.st_ino,
                stat.S_IMODE(information.st_mode),
                information.st_size,
                information.st_mtime_ns,
                information.st_ctime_ns,
            )
        )
    return tuple(
        sorted(identity, key=lambda row: (str(row[0]), str(row[1]).encode("utf-8")))
    )


def authenticate_repository(
    root: Path,
    *,
    expected_head: str | None = None,
    expected_tree: str | None = None,
) -> AuthenticatedRepositorySnapshot:
    """Authenticate one exact offline HEAD snapshot without requiring history.

    A shallow checkout is valid when its current commit, tree, index, and all
    referenced blobs are locally present.  Parent/base objects and refs are
    intentionally not consulted.
    """
    lexical_root = _checked_directory(Path(root), "repository root")
    source_identity = _directory_chain_identity(lexical_root)
    git_directory, index_raw, parsed_index = _validate_git_metadata(lexical_root)
    git_information = git_directory.lstat()
    git_identity = (git_information.st_dev, git_information.st_ino)
    _provenance_checkpoint(
        "after_initial_metadata_validation",
        source_root=lexical_root,
    )

    object_format = _git(lexical_root, "rev-parse", "--show-object-format").strip()
    _require(object_format == b"sha1", "repository object format must be SHA-1")
    try:
        head = _git(lexical_root, "rev-parse", "--verify", "HEAD^{commit}").strip().decode("ascii")
        tree = _git(lexical_root, "rev-parse", "--verify", "HEAD^{tree}").strip().decode("ascii")
    except UnicodeDecodeError as exc:
        raise RepositoryProvenanceError("HEAD/tree identity is not ASCII") from exc
    _require(_OID.fullmatch(head) is not None and _OID.fullmatch(tree) is not None, "invalid HEAD/tree identity")
    if expected_head is not None:
        _require(head == expected_head, f"HEAD identity drift: expected {expected_head}, observed {head}")
    if expected_tree is not None:
        _require(tree == expected_tree, f"tree identity drift: expected {expected_tree}, observed {tree}")

    plumbing_index_entries = _parse_index_entries(
        _git(lexical_root, "ls-files", "--stage", "-z"),
        len(parsed_index.entries),
    )
    _require(
        parsed_index.entries == plumbing_index_entries,
        "native Git index parse differs from canonical plumbing",
    )
    index_entries = parsed_index.entries
    index_paths = tuple(entry.path for entry in index_entries)
    for arguments, label in (
        (("ls-files", "-t", "-z"), "skip-worktree inventory"),
        (("ls-files", "-v", "-z"), "assume-unchanged inventory"),
        (("ls-files", "-f", "-z"), "fsmonitor-valid inventory"),
    ):
        _require(
            _parse_tagged_paths(_git(lexical_root, *arguments), label) == index_paths,
            f"{label} path/order drift",
        )
    _require_zero_index_debug_flags(
        _git(lexical_root, "ls-files", "--debug", "-z"),
        index_paths,
    )
    _require(
        _git(lexical_root, "rev-parse", "--shared-index-path").strip() == b"",
        "split Git index prohibited",
    )

    tree_entries = _parse_tree_entries(
        _git(lexical_root, "ls-tree", "-r", "-z", "--full-tree", head)
    )
    _require(index_entries == tree_entries, "Git index differs from exact HEAD tree")
    complete_tree_entries, descendant_trees = _parse_complete_tree_inventory(
        _git(lexical_root, "ls-tree", "-r", "-t", "-z", "--full-tree", head)
    )
    _require(
        complete_tree_entries == tree_entries,
        "complete Git tree inventory differs from leaf inventory",
    )
    _validate_cache_tree_semantics(
        parsed_index.cache_tree,
        root_tree=tree,
        descendant_trees=descendant_trees,
        entries=tree_entries,
    )
    graph_types = {
        head: b"commit",
        tree: b"tree",
        **{oid: b"tree" for oid in descendant_trees.values()},
    }
    graph_objects = _read_git_objects(lexical_root, graph_types)
    _require(
        graph_objects[head].startswith(b"tree " + tree.encode("ascii") + b"\n"),
        "HEAD commit does not bind the observed root tree",
    )
    entry_map = {entry.path: entry for entry in tree_entries}
    blobs = _read_git_blobs(lexical_root, (entry.oid for entry in tree_entries))
    _validate_manifest(entry_map, blobs)
    worktree_identity = _scan_and_bind_worktree(lexical_root, entry_map, blobs)
    _provenance_checkpoint("after_worktree_scan", source_root=lexical_root)

    final_git_directory, final_index_raw, final_parsed_index = _validate_git_metadata(
        lexical_root
    )
    _require(final_index_raw == index_raw, "Git index drifted during provenance capture")
    _require(
        final_parsed_index == parsed_index,
        "parsed Git index drifted during provenance capture",
    )
    _require(
        _git(lexical_root, "rev-parse", "--verify", "HEAD^{commit}").strip() == head.encode("ascii"),
        "HEAD drifted during provenance capture",
    )
    _require(
        _git(lexical_root, "rev-parse", "--verify", "HEAD^{tree}").strip() == tree.encode("ascii"),
        "HEAD tree drifted during provenance capture",
    )
    _require(
        _directory_chain_identity(lexical_root) == source_identity,
        "repository root/ancestor identity drifted during provenance capture",
    )
    final_git_information = final_git_directory.lstat()
    _require(
        (final_git_information.st_dev, final_git_information.st_ino) == git_identity,
        "physical Git directory drifted during provenance capture",
    )
    final_worktree_identity = _scan_and_bind_worktree(lexical_root, entry_map, blobs)
    _require(
        final_worktree_identity == worktree_identity,
        "worktree identity drifted during provenance capture",
    )

    snapshot_entries = tuple(
        SnapshotEntry(
            path=entry.path,
            mode=entry.mode,
            oid=entry.oid,
            sha256=hashlib.sha256(blobs[entry.oid]).hexdigest(),
            raw=blobs[entry.oid],
        )
        for entry in tree_entries
    )
    return AuthenticatedRepositorySnapshot(
        _source_root=lexical_root,
        head=head,
        tree=tree,
        index_version=parsed_index.version,
        entries=snapshot_entries,
        _index_raw=index_raw,
        _source_identity=source_identity,
        _git_identity=git_identity,
        _worktree_identity=worktree_identity,
    )


def harden_authenticated_worktree_for_bytecode_free_dispatch(
    snapshot: AuthenticatedRepositorySnapshot,
    *,
    environment: Mapping[str, str] | None = None,
) -> AuthenticatedRepositorySnapshot:
    """Make one authenticated Actions worktree cache-proof for a frozen job.

    The owner-approved workflow cannot be edited merely to add ``python -B``
    to later package invocations.  After the exact dispatch tree has passed
    provenance and runtime-binding validation, its repository directories are
    therefore made read-only for the remainder of that one ephemeral job.
    Nothing is removed, copied, ignored, or reclassified.  A pre-existing
    cache, unknown file, context mismatch, symlink, race, or writable
    postcondition fails before the job can continue.

    This operation is intentionally separate from ``authenticate_repository``
    and imported validator semantics.  It is suitable only for the runtime-
    binding CLI in the exact frozen GitHub Actions workflow.
    """

    _require(
        isinstance(snapshot, AuthenticatedRepositorySnapshot),
        "worktree hardening requires an authenticated snapshot",
    )
    root = _checked_directory(snapshot._source_root, "authenticated worktree root")
    values = dict(os.environ if environment is None else environment)
    expected_workflow_ref = (
        f"{_R11A_REPOSITORY}/.github/workflows/{_R11A_WORKFLOW_FILE}"
        f"@{_R11A_MAIN_REF}"
    )
    expected_environment = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": _R11A_REPOSITORY,
        "CURRENT_REPOSITORY": _R11A_REPOSITORY,
        "GITHUB_WORKFLOW": _R11A_WORKFLOW_NAME,
        "GITHUB_WORKFLOW_REF": expected_workflow_ref,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": _R11A_MAIN_REF,
        "GITHUB_SHA": snapshot.head,
        "DISPATCH_SHA": snapshot.head,
        "GITHUB_RUN_ATTEMPT": "1",
        "CURRENT_RUN_ATTEMPT": "1",
        "GITHUB_WORKSPACE": str(root),
    }
    for key, expected in expected_environment.items():
        _require(
            values.get(key) == expected,
            f"worktree hardening GitHub context drift: {key}",
        )
    run_id = values.get("GITHUB_RUN_ID")
    _require(
        run_id is not None and run_id.isascii() and run_id.isdecimal() and int(run_id) > 0,
        "worktree hardening GitHub run ID is invalid",
    )
    _require(
        values.get("CURRENT_RUN_ID") == run_id,
        "worktree hardening current/GitHub run ID mismatch",
    )
    _require(
        not hasattr(os, "geteuid") or os.geteuid() != 0,
        "worktree hardening refuses a root process",
    )

    # Re-authenticate immediately before the irreversible fail-closed mode
    # change.  This catches material added between the caller's validation and
    # this boundary, including synthetic cache-like files.
    before = authenticate_repository(
        root,
        expected_head=snapshot.head,
        expected_tree=snapshot.tree,
    )
    _require(before.entries == snapshot.entries, "authenticated snapshot drift before hardening")

    expected_directories: set[str] = {""}
    for entry in snapshot.entries:
        for parent in PurePosixPath(entry.path).parents:
            relative = parent.as_posix()
            if relative != ".":
                expected_directories.add(relative)

    observed_directories: dict[str, tuple[int, int]] = {}
    stack: list[tuple[Path, str]] = [(root, "")]
    while stack:
        directory, relative = stack.pop()
        try:
            information = directory.lstat()
        except OSError as exc:
            raise RepositoryProvenanceError(
                f"cannot inspect worktree directory before hardening: {relative or '.'}"
            ) from exc
        _require(
            stat.S_ISDIR(information.st_mode) and not stat.S_ISLNK(information.st_mode),
            f"non-physical worktree directory before hardening: {relative or '.'}",
        )
        observed_directories[relative] = (information.st_dev, information.st_ino)
        try:
            children = sorted(os.scandir(directory), key=lambda child: child.name.encode("utf-8"))
        except (OSError, UnicodeError) as exc:
            raise RepositoryProvenanceError(
                f"cannot scan worktree directory before hardening: {relative or '.'}"
            ) from exc
        for child in children:
            if relative == "" and child.name == ".git":
                continue
            try:
                child_information = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise RepositoryProvenanceError(
                    f"cannot inspect worktree child before hardening: {child.path}"
                ) from exc
            if stat.S_ISDIR(child_information.st_mode):
                child_relative = child.name if not relative else f"{relative}/{child.name}"
                _validate_relative_path(child_relative)
                stack.append((Path(child.path), child_relative))
    _require(
        set(observed_directories) == expected_directories,
        "worktree directory inventory drift before hardening",
    )

    directory_flag = getattr(os, "O_DIRECTORY", 0)
    nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
    for relative in sorted(
        expected_directories,
        key=lambda value: (value.count("/"), value.encode("utf-8")),
        reverse=True,
    ):
        directory = root if relative == "" else root / PurePosixPath(relative)
        try:
            descriptor = os.open(directory, os.O_RDONLY | directory_flag | nofollow_flag)
        except OSError as exc:
            raise RepositoryProvenanceError(
                f"cannot open worktree directory for hardening: {relative or '.'}"
            ) from exc
        try:
            before_mode = os.fstat(descriptor)
            _require(
                stat.S_ISDIR(before_mode.st_mode),
                f"worktree hardening target is not directory: {relative or '.'}",
            )
            _require(
                (before_mode.st_dev, before_mode.st_ino) == observed_directories[relative],
                f"worktree directory replaced before hardening: {relative or '.'}",
            )
            os.fchmod(descriptor, stat.S_IMODE(before_mode.st_mode) & ~0o222)
            after_mode = os.fstat(descriptor)
            _require(
                (after_mode.st_dev, after_mode.st_ino)
                == (before_mode.st_dev, before_mode.st_ino),
                f"worktree directory replaced during hardening: {relative or '.'}",
            )
            _require(
                stat.S_IMODE(after_mode.st_mode) & 0o222 == 0,
                f"worktree directory remains mode-writable: {relative or '.'}",
            )
        except OSError as exc:
            raise RepositoryProvenanceError(
                f"cannot harden worktree directory: {relative or '.'}"
            ) from exc
        finally:
            os.close(descriptor)

    for relative in expected_directories:
        directory = root if relative == "" else root / PurePosixPath(relative)
        information = directory.lstat()
        _require(
            (information.st_dev, information.st_ino) == observed_directories[relative]
            and stat.S_ISDIR(information.st_mode)
            and not stat.S_ISLNK(information.st_mode),
            f"worktree directory identity drift after hardening: {relative or '.'}",
        )
        _require(
            stat.S_IMODE(information.st_mode) & 0o222 == 0,
            f"worktree directory writable after hardening: {relative or '.'}",
        )
        _require(
            not os.access(directory, os.W_OK),
            f"worktree directory effectively writable after hardening: {relative or '.'}",
        )

    return authenticate_repository(
        root,
        expected_head=snapshot.head,
        expected_tree=snapshot.tree,
    )


def materialize_snapshot(
    snapshot: AuthenticatedRepositorySnapshot,
    destination: Path,
) -> None:
    _require(
        isinstance(snapshot, AuthenticatedRepositorySnapshot),
        "snapshot has unexpected type",
    )
    destination = Path(destination)
    _require(destination.is_absolute(), "snapshot destination must be absolute")
    _require(".." not in destination.parts, "snapshot destination contains traversal")
    parent = _checked_directory(destination.parent, "snapshot destination parent")
    destination = parent / destination.name
    _require(not destination.exists() and not destination.is_symlink(), "snapshot destination already exists")
    try:
        destination.relative_to(snapshot._source_root)
    except ValueError:
        pass
    else:
        raise RepositoryProvenanceError("snapshot destination may not be inside source repository")
    try:
        snapshot._source_root.relative_to(destination)
    except ValueError:
        pass
    else:
        raise RepositoryProvenanceError("snapshot destination may not contain source repository")

    _require(
        hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"),
        "snapshot construction requires no-follow directory descriptors",
    )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    parent_descriptor = os.open(parent, directory_flags)
    root_descriptor = -1
    try:
        _validate_relative_path(destination.name)
        os.mkdir(destination.name, 0o700, dir_fd=parent_descriptor)
        root_descriptor = os.open(
            destination.name,
            directory_flags,
            dir_fd=parent_descriptor,
        )
        _require_descriptor_path(root_descriptor, destination, "snapshot root")
        checkpoint_offset = len(snapshot.entries) // 2
        for offset, entry in enumerate(snapshot.entries):
            relative = _validate_relative_path(entry.path)
            parts = PurePosixPath(relative).parts
            parent_fd = _open_snapshot_directory(
                root_descriptor,
                parts[:-1],
                create=True,
            )
            descriptor = -1
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                flags |= getattr(os, "O_CLOEXEC", 0)
                descriptor = os.open(parts[-1], flags, 0o600, dir_fd=parent_fd)
                information = os.fstat(descriptor)
                _require(
                    stat.S_ISREG(information.st_mode) and information.st_nlink == 1,
                    f"snapshot target is not a private regular file: {relative}",
                )
                view = memoryview(entry.raw)
                while view:
                    written = os.write(descriptor, view)
                    _require(written > 0, f"short snapshot write: {relative}")
                    view = view[written:]
                os.fsync(descriptor)
                os.fchmod(descriptor, 0o755 if entry.mode == 0o100755 else 0o644)
            except OSError as exc:
                raise RepositoryProvenanceError(
                    f"cannot materialize authenticated blob: {relative}"
                ) from exc
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                os.close(parent_fd)
            if offset == checkpoint_offset:
                _provenance_checkpoint(
                    "during_snapshot_materialization",
                    source_root=snapshot._source_root,
                    snapshot_root=destination,
                )
                _require_descriptor_path(root_descriptor, destination, "snapshot root")
        os.fsync(root_descriptor)
    except FileExistsError as exc:
        raise RepositoryProvenanceError("snapshot destination already exists") from exc
    finally:
        if root_descriptor >= 0:
            os.close(root_descriptor)
        os.close(parent_descriptor)


def _require_descriptor_path(descriptor: int, path: Path, label: str) -> None:
    opened = os.fstat(descriptor)
    try:
        observed = path.lstat()
    except OSError as exc:
        raise RepositoryProvenanceError(f"{label} path was removed") from exc
    _require(
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and (opened.st_dev, opened.st_ino) == (observed.st_dev, observed.st_ino),
        f"{label} path identity drift",
    )


def _open_snapshot_directory(
    root_descriptor: int,
    parts: tuple[str, ...],
    *,
    create: bool,
) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    current = os.dup(root_descriptor)
    try:
        for part in parts:
            _require("/" not in part and part not in {"", ".", ".."}, "unsafe snapshot component")
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
            following = os.open(part, flags, dir_fd=current)
            information = os.fstat(following)
            _require(
                stat.S_ISDIR(information.st_mode),
                f"snapshot ancestor is not a directory: {part}",
            )
            os.close(current)
            current = following
        return current
    except OSError as exc:
        os.close(current)
        raise RepositoryProvenanceError(
            "snapshot directory traversal was replaced or escaped"
        ) from exc
    except BaseException:
        os.close(current)
        raise


def _validate_materialized_snapshot(
    snapshot: AuthenticatedRepositorySnapshot,
    root: Path,
    *,
    read_only: bool,
) -> None:
    root = _checked_directory(root, "authenticated snapshot root")
    expected_files = {entry.path: entry for entry in snapshot.entries}
    expected_directories: set[str] = {""}
    for relative in expected_files:
        for parent in PurePosixPath(relative).parents:
            rendered = parent.as_posix()
            if rendered != ".":
                expected_directories.add(rendered)

    observed_files: set[str] = set()
    observed_directories: set[str] = {""}
    stack: list[tuple[Path, PurePosixPath | None]] = [(root, None)]
    while stack:
        directory, prefix = stack.pop()
        directory_information = directory.lstat()
        _require(
            stat.S_ISDIR(directory_information.st_mode)
            and not stat.S_ISLNK(directory_information.st_mode),
            "authenticated snapshot directory is not physical",
        )
        if read_only:
            _require(
                stat.S_IMODE(directory_information.st_mode) & 0o222 == 0,
                "authenticated snapshot directory is writable",
            )
        for child in sorted(os.scandir(directory), key=lambda item: item.name.encode("utf-8")):
            information = child.stat(follow_symlinks=False)
            relative_path = PurePosixPath(child.name) if prefix is None else prefix / child.name
            relative = _validate_relative_path(relative_path.as_posix())
            _require(not stat.S_ISLNK(information.st_mode), f"snapshot symlink prohibited: {relative}")
            if stat.S_ISDIR(information.st_mode):
                observed_directories.add(relative)
                stack.append((Path(child.path), relative_path))
                continue
            _require(stat.S_ISREG(information.st_mode), f"snapshot special file prohibited: {relative}")
            _require(information.st_nlink == 1, f"snapshot hard-link prohibited: {relative}")
            _require(relative in expected_files, f"unexpected authenticated snapshot file: {relative}")
            entry = expected_files[relative]
            raw, opened = _read_regular_file(Path(child.path), "authenticated snapshot file")
            _require(raw == entry.raw, f"authenticated snapshot byte drift: {relative}")
            _require(
                bool(opened.st_mode & 0o111) == (entry.mode == 0o100755),
                f"authenticated snapshot executable mode drift: {relative}",
            )
            if read_only:
                _require(
                    stat.S_IMODE(opened.st_mode) & 0o222 == 0,
                    f"authenticated snapshot file is writable: {relative}",
                )
            observed_files.add(relative)
    _require(observed_files == set(expected_files), "authenticated snapshot file inventory drift")
    _require(observed_directories == expected_directories, "authenticated snapshot directory inventory drift")


def _set_materialized_tree_writable(root: Path, *, writable: bool) -> None:
    try:
        root_information = root.lstat()
    except OSError:
        return
    if not stat.S_ISDIR(root_information.st_mode) or stat.S_ISLNK(root_information.st_mode):
        if writable:
            return
        raise RepositoryProvenanceError("authenticated snapshot root is not physical")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    root_descriptor = os.open(root, flags)

    def apply(directory_descriptor: int, relative: str) -> None:
        try:
            children = sorted(
                os.scandir(directory_descriptor),
                key=lambda child: child.name.encode("utf-8"),
            )
        except (OSError, UnicodeError) as exc:
            raise RepositoryProvenanceError(
                f"cannot scan snapshot mode boundary: {relative or '.'}"
            ) from exc
        for child in children:
            information = child.stat(follow_symlinks=False)
            child_relative = child.name if not relative else f"{relative}/{child.name}"
            if stat.S_ISDIR(information.st_mode) and not stat.S_ISLNK(information.st_mode):
                child_descriptor = os.open(
                    child.name,
                    flags,
                    dir_fd=directory_descriptor,
                )
                try:
                    apply(child_descriptor, child_relative)
                finally:
                    os.close(child_descriptor)
                continue
            if writable:
                continue
            _require(
                stat.S_ISREG(information.st_mode)
                and not stat.S_ISLNK(information.st_mode)
                and information.st_nlink == 1,
                f"snapshot non-private file before read-only seal: {child_relative}",
            )
            file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            file_descriptor = os.open(
                child.name,
                file_flags,
                dir_fd=directory_descriptor,
            )
            try:
                opened = os.fstat(file_descriptor)
                _require(
                    (opened.st_dev, opened.st_ino)
                    == (information.st_dev, information.st_ino),
                    f"snapshot file replaced before read-only seal: {child_relative}",
                )
                _require(
                    stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1,
                    f"snapshot file gained an alias before read-only seal: {child_relative}",
                )
                os.fchmod(file_descriptor, 0o555 if opened.st_mode & 0o111 else 0o444)
            finally:
                os.close(file_descriptor)
        os.fchmod(directory_descriptor, 0o700 if writable else 0o500)

    try:
        apply(root_descriptor, "")
    finally:
        os.close(root_descriptor)


def _require_same_capture(
    expected: AuthenticatedRepositorySnapshot,
    observed: AuthenticatedRepositorySnapshot,
    label: str,
) -> None:
    _require(observed.head == expected.head, f"HEAD drift {label}")
    _require(observed.tree == expected.tree, f"tree drift {label}")
    _require(observed.index_version == expected.index_version, f"index version drift {label}")
    _require(observed._index_raw == expected._index_raw, f"index bytes drift {label}")
    _require(observed.entries == expected.entries, f"authenticated blob drift {label}")
    _require(observed._source_identity == expected._source_identity, f"source ancestor drift {label}")
    _require(observed._git_identity == expected._git_identity, f"Git directory drift {label}")
    _require(observed._worktree_identity == expected._worktree_identity, f"worktree identity drift {label}")


@contextmanager
def open_authenticated_repository(
    root: Path,
    *,
    expected_head: str | None = None,
    expected_tree: str | None = None,
) -> Iterator[AuthenticatedRepository]:
    """Yield one read-only semantic root and reject persistent source drift."""

    initial = authenticate_repository(
        root,
        expected_head=expected_head,
        expected_tree=expected_tree,
    )
    temporary = tempfile.TemporaryDirectory(prefix="r11a-authenticated-")
    destination = Path(temporary.name) / "repository"
    watcher: _SnapshotWatcher | None = None
    try:
        materialize_snapshot(initial, destination)
        _validate_materialized_snapshot(initial, destination, read_only=False)
        _set_materialized_tree_writable(destination, writable=False)
        _validate_materialized_snapshot(initial, destination, read_only=True)
        watcher = _SnapshotWatcher.start(destination)
        _provenance_checkpoint(
            "after_snapshot_materialization",
            source_root=initial._source_root,
            snapshot_root=destination,
        )
        watcher.require_clean("after snapshot materialization")
        _validate_materialized_snapshot(initial, destination, read_only=True)
        _provenance_checkpoint(
            "before_semantic_validation",
            source_root=initial._source_root,
            snapshot_root=destination,
        )
        watcher.require_clean("before semantic validation")
        _validate_materialized_snapshot(initial, destination, read_only=True)
        before_semantic = authenticate_repository(
            initial._source_root,
            expected_head=initial.head,
            expected_tree=initial.tree,
        )
        _require_same_capture(initial, before_semantic, "before semantic validation")
        watcher.require_clean("after source revalidation")
        _validate_materialized_snapshot(initial, destination, read_only=True)
        authenticated = AuthenticatedRepository(
            snapshot_root=destination,
            head=initial.head,
            tree=initial.tree,
            index_version=initial.index_version,
            entries=initial.entries,
            _source_root=initial._source_root,
            _watcher=watcher,
        )
        try:
            yield authenticated
        except BaseException:
            raise
        else:
            _provenance_checkpoint(
                "before_final_success_revalidation",
                source_root=initial._source_root,
                snapshot_root=destination,
            )
            watcher.require_clean("before final success revalidation")
            _validate_materialized_snapshot(initial, destination, read_only=True)
            final = authenticate_repository(
                initial._source_root,
                expected_head=initial.head,
                expected_tree=initial.tree,
            )
            _require_same_capture(initial, final, "before successful return")
            watcher.require_clean("at authenticated context success")
            _validate_materialized_snapshot(initial, destination, read_only=True)
    finally:
        try:
            if watcher is not None:
                watcher.close()
        finally:
            try:
                _set_materialized_tree_writable(destination, writable=True)
            finally:
                temporary.cleanup()


def authenticated_repository_checkpoint(
    authenticated: AuthenticatedRepository,
    label: str = "during_semantic_validation",
) -> None:
    _require(
        isinstance(authenticated, AuthenticatedRepository),
        "semantic checkpoint requires an authenticated repository context",
    )
    _require(label == "during_semantic_validation", "unsupported semantic checkpoint")
    _require(
        authenticated._watcher is not None,
        "authenticated repository context has no lifetime watcher",
    )
    authenticated._watcher.require_clean("before semantic checkpoint")
    expected = AuthenticatedRepositorySnapshot(
        _source_root=authenticated._source_root,
        head=authenticated.head,
        tree=authenticated.tree,
        index_version=authenticated.index_version,
        entries=authenticated.entries,
        _index_raw=b"",
        _source_identity=(),
        _git_identity=(0, 0),
        _worktree_identity=(),
    )
    _validate_materialized_snapshot(
        expected,
        authenticated.snapshot_root,
        read_only=True,
    )
    _provenance_checkpoint(
        label,
        source_root=authenticated._source_root,
        snapshot_root=authenticated.snapshot_root,
    )
    authenticated._watcher.require_clean("during semantic checkpoint")
    _validate_materialized_snapshot(
        expected,
        authenticated.snapshot_root,
        read_only=True,
    )


def authenticated_repository_copy(
    root: Path,
    *,
    expected_head: str | None = None,
    expected_tree: str | None = None,
) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    """Adapter for tests that need a fresh exact, cache-free repository copy.

    The returned directory has no `.git` metadata and is materialized solely
    from authenticated Git blob bytes.  The caller owns and must clean up the
    returned ``TemporaryDirectory``.
    """
    snapshot = authenticate_repository(
        root,
        expected_head=expected_head,
        expected_tree=expected_tree,
    )
    temporary = tempfile.TemporaryDirectory()
    destination = Path(temporary.name) / "repository"
    try:
        materialize_snapshot(snapshot, destination)
    except BaseException:
        temporary.cleanup()
        raise
    return temporary, destination


def project_historical_r11a_implementation_snapshot(root: Path) -> None:
    """Restore the one self-sealed test blob in an authenticated temp copy.

    The inert implementation contract predates the post-G2 provenance helper
    and seals the then-current implementation test itself.  The live test must
    use ``authenticated_repository_copy``; the historical validator must see
    the byte-exact earlier test that its immutable contract sealed.  Derive
    that old blob only from the authenticated live blob using two exact,
    single-occurrence transformations and require its frozen SHA-256 before
    writing it into the already isolated temporary snapshot.

    This is deliberately not part of snapshot authentication and never runs
    for G2/current-state validation.  It cannot omit a path, accept arbitrary
    bytes, or alter the physical source repository.
    """

    snapshot_root = _checked_directory(Path(root), "historical snapshot root")
    target = snapshot_root / _HISTORICAL_R11A_IMPLEMENTATION_TEST
    current, information = _read_regular_file(
        target,
        "authenticated live implementation test",
    )
    _require(
        stat.S_ISREG(information.st_mode),
        "authenticated live implementation test is not regular",
    )

    current_import = (
        b"from governance.r11a_repository_provenance import (\n"
        b"    authenticated_repository_copy,\n"
        b"    project_historical_r11a_implementation_snapshot,\n"
        b")\n"
    )
    historical_import = b""
    current_setup = (
        b"        temporary, historical_root = authenticated_repository_copy(\n"
        b"            ROOT,\n"
        b"        )\n"
        b"        with temporary:\n"
        b"            project_historical_r11a_implementation_snapshot(historical_root)\n"
    )
    historical_setup = (
        b"        with tempfile.TemporaryDirectory() as directory:\n"
        b"            historical_root = Path(directory) / \"repository\"\n"
        b"            shutil.copytree(\n"
        b"                ROOT,\n"
        b"                historical_root,\n"
        b"                ignore=shutil.ignore_patterns(\".git\", \"__pycache__\", \"*.pyc\", \"*.pyo\"),\n"
        b"            )\n"
    )
    _require(
        current.count(current_import) == 1 and current.count(current_setup) == 1,
        "live implementation test cannot be projected to its sealed historical form",
    )
    historical = current.replace(
        current_import,
        historical_import,
        1,
    ).replace(
        current_setup,
        historical_setup,
        1,
    )
    _require(
        hashlib.sha256(historical).hexdigest()
        == _HISTORICAL_R11A_IMPLEMENTATION_TEST_SHA256,
        "projected historical implementation test digest drift",
    )
    target.write_bytes(historical)


__all__ = [
    "AuthenticatedRepository",
    "AuthenticatedRepositorySnapshot",
    "MANIFEST_PATH",
    "RepositoryProvenanceError",
    "SnapshotEntry",
    "authenticate_repository",
    "authenticated_repository_checkpoint",
    "authenticated_repository_copy",
    "harden_authenticated_worktree_for_bytecode_free_dispatch",
    "materialize_snapshot",
    "open_authenticated_repository",
    "project_historical_r11a_implementation_snapshot",
]
