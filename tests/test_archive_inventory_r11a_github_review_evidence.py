from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from governance import r11a_github_review_evidence as evidence


ROOT = Path(__file__).resolve().parents[1]
GATE_ID = "R11A_RUNTIME_BINDING_REVIEW"
HEAD = "a" * 40
REPOSITORY_ID = evidence.REPOSITORY_ID
PR_NUMBER = 151
REVIEW_ID = 6000000001
REVIEW_NODE_ID = "PRR_kwDOReviewEvidence"
OWNER_LOGIN = "Mathisve1"
OWNER_USER_ID = 163474992

REVIEW_MARKER_LABELS = (
    "repository",
    "pull request",
    "event",
    "verdict",
    "gate",
    "reviewed head",
    "reviewed tree",
    "target stage",
    "target bundle",
    "immediate predecessor stage",
    "immediate predecessor head",
    "immediate predecessor tree",
    "immediate predecessor bundle",
    "reviewer model",
    "reviewer login",
    "reviewer user ID",
    "reviewer author association",
    "reviewer repository permission",
    "github approval",
    "third-party independence",
    "merge authority",
    "AWS/IAM/OIDC/STS/S3 authority",
    "workflow/release/activation/runtime/diagnostic authority",
    "human substantive responsibility",
)


def _json_body(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _payload(endpoint: str, value: Any) -> dict[str, Any]:
    raw = _json_body(value)
    return {
        "endpoint": endpoint,
        "http_status": 200,
        "content_type": "application/json",
        "encoding": "base64",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "body_base64": base64.b64encode(raw).decode("ascii"),
    }


def _payload_value(wrapper: dict[str, Any]) -> Any:
    return json.loads(base64.b64decode(wrapper["body_base64"], validate=True))


def _replace_payload(wrapper: dict[str, Any], value: Any) -> None:
    replacement = _payload(wrapper["endpoint"], value)
    wrapper.clear()
    wrapper.update(replacement)


def _git_blob_oid(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _blob_capture(raw: bytes) -> tuple[str, dict[str, Any]]:
    oid = _git_blob_oid(raw)
    api_path = f"/repos/{evidence.REPOSITORY_FULL_NAME}/git/blobs/{oid}"
    return oid, _payload(
        api_path,
        {
            "sha": oid,
            "size": len(raw),
            "url": "https://api.github.com" + api_path,
            "encoding": "base64",
            "content": base64.b64encode(raw).decode("ascii"),
        },
    )


def _git_tree_oid(entries: list[tuple[str, str, str]]) -> str:
    body = bytearray()
    for name, mode, oid in sorted(
        entries,
        key=lambda item: item[0].encode("utf-8")
        + (b"/" if item[1] == "040000" else b""),
    ):
        body.extend((mode.lstrip("0") if mode == "040000" else mode).encode("ascii"))
        body.extend(b" ")
        body.extend(name.encode("utf-8"))
        body.extend(b"\0")
        body.extend(bytes.fromhex(oid))
    return hashlib.sha1(f"tree {len(body)}\0".encode("ascii") + body).hexdigest()


def _tree_capture(
    blobs: dict[str, bytes],
) -> tuple[str, dict[str, Any], dict[str, dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    wrappers: dict[str, dict[str, Any]] = {}
    blob_oids: dict[str, str] = {}
    for relative in sorted(blobs, key=lambda item: item.encode("utf-8")):
        raw = blobs[relative]
        oid, wrapper = _blob_capture(raw)
        blob_oids[relative] = oid
        wrappers[relative] = wrapper
        entries.append(
            {
                "path": relative,
                "mode": "100644",
                "type": "blob",
                "sha": oid,
                "size": len(raw),
                "url": (
                    "https://api.github.com/repos/"
                    f"{evidence.REPOSITORY_FULL_NAME}/git/blobs/{oid}"
                ),
            }
        )

    directories: set[str] = set()
    for relative in blobs:
        parts = relative.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            directories.add("/".join(parts[:index]))
    directory_oids: dict[str, str] = {}
    for directory in sorted(
        {"", *directories},
        key=lambda item: len(item.split("/")) if item else 0,
        reverse=True,
    ):
        children: list[tuple[str, str, str]] = []
        for relative, oid in blob_oids.items():
            parent, _, name = relative.rpartition("/")
            if parent == directory:
                children.append((name, "100644", oid))
        for child_directory, oid in directory_oids.items():
            parent, _, name = child_directory.rpartition("/")
            if parent == directory:
                children.append((name, "040000", oid))
        directory_oids[directory] = _git_tree_oid(children)

    tree_sha = directory_oids[""]
    for relative in sorted(directories, key=lambda item: item.encode("utf-8")):
        oid = directory_oids[relative]
        entries.append(
            {
                "path": relative,
                "mode": "040000",
                "type": "tree",
                "sha": oid,
                "url": (
                    "https://api.github.com/repos/"
                    f"{evidence.REPOSITORY_FULL_NAME}/git/trees/{oid}"
                ),
            }
        )
    entries.sort(key=lambda item: item["path"].encode("utf-8"))
    api_path = (
        f"/repos/{evidence.REPOSITORY_FULL_NAME}/git/trees/{tree_sha}?recursive=1"
    )
    tree_payload = _payload(
        api_path,
        {
            "sha": tree_sha,
            "url": (
                "https://api.github.com/repos/"
                f"{evidence.REPOSITORY_FULL_NAME}/git/trees/{tree_sha}"
            ),
            "tree": entries,
            "truncated": False,
        },
    )
    return tree_sha, tree_payload, wrappers


def _synthetic_lineage(final_tree: str) -> tuple[evidence.ReviewEvidenceIdentity, ...]:
    gates = tuple(evidence.GATE_REGISTRY)
    lineage: list[evidence.ReviewEvidenceIdentity] = []
    predecessor_head = evidence.SEED_REVIEWS[-1].reviewed_head
    predecessor_tree = evidence.SEED_REVIEWS[-1].reviewed_tree
    for index, gate_id in enumerate(gates[:-1], start=1):
        contract = evidence.GATE_REGISTRY[gate_id]
        head = f"{index + 100:040x}"
        tree = final_tree if gate_id == gates[-2] else f"{index + 200:040x}"
        identity = evidence.ReviewEvidenceIdentity(
            gate_id=gate_id,
            evidence_relative=contract.evidence_relative,
            evidence_sha256=f"{index + 300:064x}",
            repository_full_name=evidence.REPOSITORY_FULL_NAME,
            repository_id=REPOSITORY_ID,
            pull_request_number=PR_NUMBER + index,
            pull_request_node_id=f"PR_LINEAGE_{index}",
            pull_request_author_login="Mathisve1",
            pull_request_author_id=111,
            review_id=7000000000 + index,
            review_node_id=f"PRR_LINEAGE_{index}",
            reviewer_login="independent-reviewer",
            reviewer_id=222,
            reviewer_author_association="COLLABORATOR",
            reviewer_repository_permission="write",
            reviewer_repository_role_name="write",
            reviewer_model=(
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
            ),
            submitted_at=f"2026-08-{index + 1:02d}T10:01:00Z",
            reviewed_commit_committed_at=f"2026-08-{index + 1:02d}T10:00:00Z",
            captured_at=f"2026-08-{index + 1:02d}T10:02:00Z",
            reviewed_head=head,
            reviewed_tree=tree,
            target_stage_id=contract.target_stage_id,
            target_bundle_sha256=f"{index + 400:064x}",
            predecessor_stage_id=contract.predecessor_stage_id,
            predecessor_reviewed_head=predecessor_head,
            predecessor_reviewed_tree=predecessor_tree,
            predecessor_bundle_sha256=f"{index + 500:064x}",
        )
        lineage.append(identity)
        predecessor_head = head
        predecessor_tree = tree
    return tuple(lineage)


class EvidenceFixture:
    def __init__(self) -> None:
        contract = evidence.GATE_REGISTRY[GATE_ID]
        gate_ids = tuple(evidence.GATE_REGISTRY)
        gate_index = gate_ids.index(GATE_ID)
        immediate_evidence = evidence.GATE_REGISTRY[
            gate_ids[gate_index - 1]
        ].evidence_relative
        self.target_blobs = {
            "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json": (
                b'{"binding":"exact"}\n'
            ),
            "governance/validate_r11a_runtime_binding_r7.py": b"# exact validator\n",
            immediate_evidence: b'{"activation_review":"exact"}\n',
        }
        self.predecessor_blobs = {
            "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json": (
                b'{"activation":"exact"}\n'
            )
        }
        earlier_subjects = {
            relative: f"subject:{relative}\n".encode("utf-8")
            for prior_gate in gate_ids[:gate_index]
            for relative in evidence.GATE_REGISTRY[prior_gate].subject_paths
            if relative not in self.predecessor_blobs
        }
        older_evidence = {
            evidence.GATE_REGISTRY[prior_gate].evidence_relative: (
                f"evidence:{prior_gate}\n".encode("utf-8")
            )
            for prior_gate in gate_ids[: gate_index - 1]
        }
        self.predecessor_tree_inputs = {
            **earlier_subjects,
            **older_evidence,
            **self.predecessor_blobs,
        }
        predecessor_tree_sha, predecessor_tree, predecessor_blob_wrappers = _tree_capture(
            self.predecessor_tree_inputs
        )
        self.lineage = _synthetic_lineage(predecessor_tree_sha)
        self.predecessor_head = self.lineage[-1].reviewed_head
        self.predecessor_tree = self.lineage[-1].reviewed_tree
        self.tree, reviewed_tree, target_blobs = _tree_capture(
            {**self.target_blobs, **self.predecessor_tree_inputs}
        )
        self.target_files = {
            path: hashlib.sha256(raw).hexdigest()
            for path, raw in self.target_blobs.items()
        }
        self.predecessor_files = {
            path: hashlib.sha256(raw).hexdigest()
            for path, raw in self.predecessor_blobs.items()
        }
        target_bundle = evidence.bundle_sha256(self.target_files)
        predecessor_bundle = evidence.bundle_sha256(self.predecessor_files)
        self.target_bundle = target_bundle
        self.predecessor_bundle = predecessor_bundle
        self.lineage = (
            *self.lineage[:-1],
            replace(
                self.lineage[-1],
                target_bundle_sha256=predecessor_bundle,
            ),
        )
        body = self.review_body(
            reviewer_model=(
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
            ),
            reviewer_login="independent-reviewer",
            reviewer_user_id=222,
            reviewer_author_association="COLLABORATOR",
            reviewer_repository_permission="write",
        )
        repository = {
            "id": REPOSITORY_ID,
            "full_name": evidence.REPOSITORY_FULL_NAME,
        }
        repository_ref = {
            "id": REPOSITORY_ID,
            "full_name": evidence.REPOSITORY_FULL_NAME,
        }
        pull_url = (
            "https://api.github.com/repos/"
            f"{evidence.REPOSITORY_FULL_NAME}/pulls/{PR_NUMBER}"
        )
        pull_request = {
            "id": 4000000001,
            "node_id": "PR_kwDOReviewEvidence",
            "number": PR_NUMBER,
            "url": pull_url,
            "created_at": "2026-08-28T09:00:00Z",
            "user": {"login": "Mathisve1", "id": 111},
            "head": {"sha": HEAD, "repo": repository_ref},
            "base": {"sha": self.predecessor_head, "repo": repository_ref},
        }
        reviewed_commit = {
            "sha": HEAD,
            "commit": {
                "tree": {"sha": self.tree},
                "committer": {"date": "2026-08-28T10:00:00Z"},
            },
        }
        review = {
            "id": REVIEW_ID,
            "node_id": REVIEW_NODE_ID,
            "state": "COMMENTED",
            "author_association": "COLLABORATOR",
            "body": body,
            "submitted_at": "2026-08-28T10:01:00Z",
            "commit_id": HEAD,
            "user": {"login": "independent-reviewer", "id": 222},
            "pull_request_url": pull_url,
        }
        prefix = f"/repos/{evidence.REPOSITORY_FULL_NAME}"
        self.envelope = {
            "schema_version": "1.1",
            "evidence_type": "EXTERNALLY_CAPTURED_GITHUB_PULL_REQUEST_REVIEW",
            "gate_id": GATE_ID,
            "selected_review_id": REVIEW_ID,
            "selected_review_node_id": REVIEW_NODE_ID,
            "reviewer_model": (
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
            ),
            "capture": {
                "capture_method": evidence.CAPTURE_METHOD,
                "captured_at": "2026-08-28T10:02:00Z",
                "integrity_scope": evidence.CAPTURE_INTEGRITY_STATUS,
                "origin_authentication": evidence.ORIGIN_AUTHENTICATION_STATUS,
                "offline_network_access": False,
            },
            "source_payloads": {
                "repository": _payload(prefix, repository),
                "pull_request": _payload(
                    f"{prefix}/pulls/{PR_NUMBER}",
                    pull_request,
                ),
                "reviewed_commit": _payload(
                    f"{prefix}/commits/{HEAD}",
                    reviewed_commit,
                ),
                "reviewed_tree": reviewed_tree,
                "predecessor_tree": predecessor_tree,
                "review_pages": [
                    _payload(
                        f"{prefix}/pulls/{PR_NUMBER}/reviews?per_page=100&page=1",
                        [review],
                    )
                ],
                "reviewer_permission": _payload(
                    (
                        f"{prefix}/collaborators/"
                        "independent-reviewer/permission"
                    ),
                    {
                        "permission": "write",
                        "role_name": "write",
                        "user": {
                            "login": "independent-reviewer",
                            "id": 222,
                        },
                    },
                ),
                "target_blobs": {
                    path: target_blobs[path] for path in self.target_blobs
                },
                "predecessor_blobs": {
                    path: predecessor_blob_wrappers[path]
                    for path in self.predecessor_blobs
                },
            },
            "reviewed_stage": {
                "stage_id": contract.target_stage_id,
                "bundle_sha256": target_bundle,
                "files": self.target_files,
            },
            "immediate_predecessor": {
                "stage_id": contract.predecessor_stage_id,
                "reviewed_head": self.predecessor_head,
                "reviewed_tree": self.predecessor_tree,
                "bundle_sha256": predecessor_bundle,
                "files": self.predecessor_files,
            },
        }

    def review_body(
        self,
        *,
        reviewer_model: str,
        reviewer_login: str,
        reviewer_user_id: int,
        reviewer_author_association: str,
        reviewer_repository_permission: str,
    ) -> str:
        contract = evidence.GATE_REGISTRY[GATE_ID]
        return "\n".join(
            (
                "GREEN",
                "",
                f"repository: `{evidence.REPOSITORY_FULL_NAME}`",
                f"pull request: `#{PR_NUMBER}`",
                "event: `COMMENTED`",
                "verdict: `GREEN`",
                f"gate: `{GATE_ID}`",
                f"reviewed head: `{HEAD}`",
                f"reviewed tree: `{self.tree}`",
                f"target stage: `{contract.target_stage_id}`",
                f"target bundle: `{self.target_bundle}`",
                f"immediate predecessor stage: `{contract.predecessor_stage_id}`",
                f"immediate predecessor head: `{self.predecessor_head}`",
                f"immediate predecessor tree: `{self.predecessor_tree}`",
                f"immediate predecessor bundle: `{self.predecessor_bundle}`",
                f"reviewer model: `{reviewer_model}`",
                f"reviewer login: `{reviewer_login}`",
                f"reviewer user ID: `{reviewer_user_id}`",
                (
                    "reviewer author association: `"
                    f"{reviewer_author_association}`"
                ),
                (
                    "reviewer repository permission: `"
                    f"{reviewer_repository_permission}`"
                ),
                "github approval: `NOT_APPROVED`",
                "third-party independence: `NOT_CLAIMED`",
                "merge authority: `NOT_GRANTED`",
                "AWS/IAM/OIDC/STS/S3 authority: `NOT_GRANTED`",
                (
                    "workflow/release/activation/runtime/diagnostic authority: "
                    "`NOT_GRANTED`"
                ),
                "human substantive responsibility: `RETAINED_BY_REVIEWER`",
            )
        )

    def reader(self, head: str, relative: str) -> bytes:
        if head == HEAD:
            return self.target_blobs[relative]
        if head == self.predecessor_head:
            return self.predecessor_blobs[relative]
        raise AssertionError("unexpected head")

    def raw(self, envelope_value: dict[str, Any] | None = None) -> bytes:
        return evidence.canonical_json_bytes(envelope_value or self.envelope)

    def write(self, root: Path, raw: bytes | None = None) -> bytes:
        encoded = self.raw() if raw is None else raw
        path = root / evidence.evidence_path(GATE_ID)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        return encoded

    def validate(
        self,
        root: Path,
        *,
        raw: bytes | None = None,
        expected_sha: str | None = None,
        expected_pr_number: int | None = PR_NUMBER,
        expected_reviewer: evidence.ReviewerPolicy | None = None,
        consumed: tuple[evidence.ReviewEvidenceIdentity, ...] | None = None,
        reader: Callable[[str, str], bytes] | None = None,
        target_files: dict[str, str] | None = None,
    ) -> evidence.ReviewEvidenceIdentity:
        encoded = self.write(root, raw)
        return evidence.validate_gate_evidence(
            root,
            GATE_ID,
            expected_evidence_sha256=(
                hashlib.sha256(encoded).hexdigest()
                if expected_sha is None
                else expected_sha
            ),
            expected_pr_number=expected_pr_number,
            expected_target_files=target_files or self.target_files,
            expected_predecessor_files=self.predecessor_files,
            expected_reviewer=expected_reviewer,
            consumed=self.lineage if consumed is None else consumed,
            reviewed_blob_reader=reader,
        )


class GithubReviewEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = EvidenceFixture()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).absolute()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_fixed_gate_registry_is_unique_and_live_tree_has_no_evidence(self) -> None:
        paths = [contract.evidence_relative for contract in evidence.GATE_REGISTRY.values()]
        self.assertEqual(11, len(paths))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(path.startswith(evidence.EVIDENCE_DIRECTORY + "/") for path in paths))
        self.assertEqual(
            (
                evidence.EVIDENCE_DIRECTORY
                + "/R11A_RUNTIME_BINDING_REVIEW_EVIDENCE.json"
            ),
            evidence.evidence_path(GATE_ID),
        )
        evidence.require_no_review_evidence(ROOT)

    def test_canonical_capture_validates_without_claiming_github_origin(self) -> None:
        identity = self.fixture.validate(
            self.root,
            expected_reviewer=evidence.ReviewerPolicy(
                expected_login="independent-reviewer",
                expected_user_id=222,
                expected_model=(
                    evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
                ),
                forbid_pull_request_author=True,
            ),
        )
        self.assertEqual(evidence.CAPTURE_INTEGRITY_STATUS, identity.integrity_status)
        self.assertEqual(
            evidence.ORIGIN_AUTHENTICATION_STATUS,
            identity.origin_authentication,
        )
        self.assertEqual(REVIEW_ID, identity.review_id)
        self.assertEqual(REVIEW_NODE_ID, identity.review_node_id)
        self.assertEqual(HEAD, identity.reviewed_head)
        self.assertEqual(self.fixture.tree, identity.reviewed_tree)
        self.assertEqual(
            evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
            identity.reviewer_model,
        )

    def test_future_pr_number_can_be_derived_but_remains_raw_payload_bound(self) -> None:
        identity = self.fixture.validate(self.root, expected_pr_number=None)
        self.assertEqual(PR_NUMBER, identity.pull_request_number)

    def test_owner_self_review_commented_green_validates_with_exact_model(self) -> None:
        allowed = (
            ("OWNER", "admin"),
            ("MEMBER", "maintain"),
            ("COLLABORATOR", "write"),
        )
        for association, permission in allowed:
            with self.subTest(association=association, permission=permission):
                changed = self._owner_envelope(
                    association=association,
                    permission=permission,
                )
                identity = self.fixture.validate(
                    self.root,
                    raw=self.fixture.raw(changed),
                    expected_reviewer=evidence.ReviewerPolicy(
                        expected_login=OWNER_LOGIN,
                        expected_user_id=OWNER_USER_ID,
                        expected_model=evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
                    ),
                )
                self.assertEqual(OWNER_LOGIN, identity.pull_request_author_login)
                self.assertEqual(OWNER_USER_ID, identity.pull_request_author_id)
                self.assertEqual(OWNER_LOGIN, identity.reviewer_login)
                self.assertEqual(OWNER_USER_ID, identity.reviewer_id)
                self.assertEqual(association, identity.reviewer_author_association)
                self.assertEqual(permission, identity.reviewer_repository_permission)
                self.assertEqual(
                    evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
                    identity.reviewer_model,
                )
                self.assertEqual(REVIEW_ID, identity.review_id)
                self.assertEqual(REVIEW_NODE_ID, identity.review_node_id)
                self.assertEqual(HEAD, identity.reviewed_head)
                self.assertEqual(self.fixture.tree, identity.reviewed_tree)
                self.assertEqual(
                    self.fixture.target_bundle,
                    identity.target_bundle_sha256,
                )
                self.assertEqual(
                    self.fixture.predecessor_bundle,
                    identity.predecessor_bundle_sha256,
                )

    def test_envelope_requires_strict_canonical_json_and_exact_schema(self) -> None:
        with self.subTest("noncanonical whitespace"):
            raw = self.fixture.raw()[:-1] + b" \n"
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "canonical JSON"):
                self.fixture.validate(self.root, raw=raw)

        with self.subTest("unknown envelope key"):
            changed = copy.deepcopy(self.fixture.envelope)
            changed["fabricated_authenticity"] = True
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "keys drift"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        with self.subTest("false origin-authentication claim"):
            changed = copy.deepcopy(self.fixture.envelope)
            changed["capture"]["origin_authentication"] = "GITHUB_ORIGIN_AUTHENTICATED"
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "falsely claims"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        with self.subTest("duplicate key"):
            raw = self.fixture.raw()
            needle = b'"gate_id":"R11A_RUNTIME_BINDING_REVIEW",'
            duplicated = raw.replace(needle, needle + needle, 1)
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "duplicate JSON key"):
                self.fixture.validate(self.root, raw=duplicated)

        for field in ("selected_review_node_id", "reviewer_model"):
            with self.subTest(missing_schema_field=field):
                changed = copy.deepcopy(self.fixture.envelope)
                changed.pop(field)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "keys drift",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_selected_review_node_and_reviewer_model_are_payload_bound(self) -> None:
        changed = copy.deepcopy(self.fixture.envelope)
        changed["selected_review_node_id"] = "PRR_wrong"
        with self.assertRaises(evidence.ReviewEvidenceError):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_review(
            changed,
            lambda value: value.__setitem__("node_id", "PRR_wrong"),
        )
        with self.assertRaises(evidence.ReviewEvidenceError):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        changed["reviewer_model"] = evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN
        with self.assertRaises(evidence.ReviewEvidenceError):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_payload_base64_hash_and_unbound_fabrication_fail_closed(self) -> None:
        changed = copy.deepcopy(self.fixture.envelope)
        wrapper = changed["source_payloads"]["review_pages"][0]
        page = _payload_value(wrapper)
        page[0]["id"] += 1
        wrapper["body_base64"] = base64.b64encode(_json_body(page)).decode("ascii")
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "payload SHA-256 mismatch"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        changed["selected_review_id"] += 1
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "selected review ID"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_wrong_repository_pr_head_tree_or_review_event_fails_closed(self) -> None:
        cases: dict[str, tuple[str, Callable[[dict[str, Any]], None]]] = {
            "repository": (
                "wrong repository",
                lambda envelope_value: self._mutate_source(
                    envelope_value,
                    "repository",
                    lambda value: value.__setitem__("full_name", "Mathisve1/wrong"),
                ),
            ),
            "pull request": (
                "wrong pull request",
                lambda envelope_value: self._mutate_source(
                    envelope_value,
                    "pull_request",
                    lambda value: value.__setitem__("number", 152),
                ),
            ),
            "head": (
                "pull-request head",
                lambda envelope_value: self._mutate_source(
                    envelope_value,
                    "pull_request",
                    lambda value: value["head"].__setitem__("sha", "d" * 40),
                ),
            ),
            "tree": (
                "reviewed recursive-tree endpoint drift",
                lambda envelope_value: self._mutate_source(
                    envelope_value,
                    "reviewed_commit",
                    lambda value: value["commit"]["tree"].__setitem__("sha", "d" * 40),
                ),
            ),
            "RED": (
                "does not start with GREEN",
                lambda envelope_value: self._mutate_review(
                    envelope_value,
                    lambda value: value.__setitem__(
                        "body",
                        value["body"].replace("GREEN", "RED"),
                    ),
                ),
            ),
            "wrong event": (
                "not COMMENTED",
                lambda envelope_value: self._mutate_review(
                    envelope_value,
                    lambda value: value.__setitem__("state", "CHANGES_REQUESTED"),
                ),
            ),
        }
        for label, (message, mutate) in cases.items():
            with self.subTest(label):
                changed = copy.deepcopy(self.fixture.envelope)
                mutate(changed)
                with self.assertRaisesRegex(evidence.ReviewEvidenceError, message):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_source(
            changed,
            "repository",
            lambda value: value.__setitem__("id", REPOSITORY_ID + 1),
        )
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "repository ID drift"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def _mutate_source(
        self,
        envelope_value: dict[str, Any],
        source: str,
        mutate: Callable[[Any], None],
    ) -> None:
        wrapper = envelope_value["source_payloads"][source]
        value = _payload_value(wrapper)
        mutate(value)
        _replace_payload(wrapper, value)

    def _mutate_review(
        self,
        envelope_value: dict[str, Any],
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        wrapper = envelope_value["source_payloads"]["review_pages"][0]
        value = _payload_value(wrapper)
        mutate(value[0])
        _replace_payload(wrapper, value)

    def _mutate_review_body(
        self,
        envelope_value: dict[str, Any],
        mutate: Callable[[str], str],
    ) -> None:
        self._mutate_review(
            envelope_value,
            lambda value: value.__setitem__("body", mutate(value["body"])),
        )

    def _replace_review_marker(
        self,
        envelope_value: dict[str, Any],
        label: str,
        replacement: str,
    ) -> None:
        prefix = f"{label}: `"

        def replace_marker(body: str) -> str:
            lines = body.splitlines()
            indexes = [
                index
                for index, line in enumerate(lines)
                if line.startswith(prefix) and line.endswith("`")
            ]
            self.assertEqual(1, len(indexes), label)
            lines[indexes[0]] = f"{label}: `{replacement}`"
            return "\n".join(lines)

        self._mutate_review_body(envelope_value, replace_marker)

    def _owner_envelope(
        self,
        *,
        association: str = "OWNER",
        permission: str = "admin",
        reviewer_login: str = OWNER_LOGIN,
        reviewer_user_id: int = OWNER_USER_ID,
        reviewer_model: str = evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
    ) -> dict[str, Any]:
        changed = copy.deepcopy(self.fixture.envelope)
        owner = {"login": OWNER_LOGIN, "id": OWNER_USER_ID}
        reviewer = {"login": reviewer_login, "id": reviewer_user_id}
        self._mutate_source(
            changed,
            "pull_request",
            lambda value: value.__setitem__("user", owner),
        )

        def make_owner_review(value: dict[str, Any]) -> None:
            value["user"] = reviewer
            value["author_association"] = association
            value["body"] = self.fixture.review_body(
                reviewer_model=reviewer_model,
                reviewer_login=reviewer_login,
                reviewer_user_id=reviewer_user_id,
                reviewer_author_association=association,
                reviewer_repository_permission=permission,
            )

        self._mutate_review(changed, make_owner_review)
        prefix = f"/repos/{evidence.REPOSITORY_FULL_NAME}"
        changed["source_payloads"]["reviewer_permission"] = _payload(
            f"{prefix}/collaborators/{reviewer_login}/permission",
            {
                "permission": permission,
                "role_name": permission,
                "user": reviewer,
            },
        )
        changed["reviewer_model"] = reviewer_model
        return changed

    def test_exact_owner_and_fully_distinct_reviewer_models_pass(self) -> None:
        owner_identity = self.fixture.validate(
            self.root,
            raw=self.fixture.raw(self._owner_envelope()),
        )
        self.assertEqual(
            evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
            owner_identity.reviewer_model,
        )
        self.assertEqual(OWNER_LOGIN, owner_identity.reviewer_login)
        self.assertEqual(OWNER_USER_ID, owner_identity.reviewer_id)

        distinct_identity = self.fixture.validate(
            self.root,
            raw=self.fixture.raw(
                self._owner_envelope(
                    reviewer_login="different-reviewer",
                    reviewer_user_id=OWNER_USER_ID + 1,
                    reviewer_model=(
                        evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
                    ),
                )
            ),
        )
        self.assertEqual(
            evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
            distinct_identity.reviewer_model,
        )
        self.assertEqual("different-reviewer", distinct_identity.reviewer_login)
        self.assertEqual(OWNER_USER_ID + 1, distinct_identity.reviewer_id)

    def test_reviewer_identity_and_configured_self_review_policy_fail_closed(self) -> None:
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "unexpected reviewer"):
            self.fixture.validate(
                self.root,
                expected_reviewer=evidence.ReviewerPolicy(
                    expected_login="different-reviewer",
                    expected_user_id=333,
                    expected_model=(
                        evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
                    ),
                ),
            )

        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_review(
            changed,
            lambda value: value.__setitem__("author_association", "NONE"),
        )
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "not repository-associated",
        ):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_source(
            changed,
            "reviewer_permission",
            lambda value: value.__setitem__("permission", "read"),
        )
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "lacks write-or-higher",
        ):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_source(
            changed,
            "reviewer_permission",
            lambda value: value["user"].__setitem__("id", 333),
        )
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "permission identity drift",
        ):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "distinct-reviewer policy",
        ):
            self.fixture.validate(
                self.root,
                raw=self.fixture.raw(changed),
                expected_reviewer=evidence.ReviewerPolicy(
                    expected_login=OWNER_LOGIN,
                    expected_user_id=OWNER_USER_ID,
                    expected_model=evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
                    forbid_pull_request_author=True,
                ),
            )

    def test_owner_review_rejects_noncommented_review_states(self) -> None:
        for state in ("APPROVED", "CHANGES_REQUESTED", "REQUEST_CHANGES"):
            with self.subTest(state=state):
                changed = self._owner_envelope()
                self._mutate_review(
                    changed,
                    lambda value, state=state: value.__setitem__("state", state),
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "not COMMENTED",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

    def test_owner_review_rejects_weak_or_missing_repository_permission(self) -> None:
        for permission in ("read", "triage"):
            with self.subTest(permission=permission):
                changed = self._owner_envelope(permission=permission)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "lacks write-or-higher",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

        changed = self._owner_envelope()
        self._mutate_source(
            changed,
            "reviewer_permission",
            lambda value: value.pop("permission"),
        )
        with self.assertRaises(evidence.ReviewEvidenceError):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        for field, value in (
            ("login", "different-reviewer"),
            ("id", OWNER_USER_ID + 1),
        ):
            with self.subTest(permission_identity_field=field):
                changed = self._owner_envelope()
                self._mutate_source(
                    changed,
                    "reviewer_permission",
                    lambda payload, field=field, value=value: payload[
                        "user"
                    ].__setitem__(field, value),
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "permission identity drift",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_owner_review_rejects_unassociated_or_partially_matching_identity(self) -> None:
        for association in ("NONE", "CONTRIBUTOR"):
            with self.subTest(association=association):
                changed = self._owner_envelope(association=association)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "not repository-associated",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

        ambiguous_cases = (
            ("mathisve1", OWNER_USER_ID, evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN),
            ("MATHISVE1", OWNER_USER_ID, evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN),
            (
                "mathisve1",
                OWNER_USER_ID + 1,
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
            ),
        )
        for reviewer_login, reviewer_user_id, reviewer_model in ambiguous_cases:
            with self.subTest(
                case_ambiguous_login=reviewer_login,
                reviewer_user_id=reviewer_user_id,
            ):
                changed = self._owner_envelope(
                    reviewer_login=reviewer_login,
                    reviewer_user_id=reviewer_user_id,
                    reviewer_model=reviewer_model,
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "reviewer login case ambiguity",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        partial_match_cases = (
            (
                OWNER_LOGIN,
                OWNER_USER_ID + 1,
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
            ),
            (
                "different-reviewer",
                OWNER_USER_ID,
                evidence.OWNER_SELF_REVIEW_COMMENTED_GREEN,
            ),
        )
        for reviewer_login, reviewer_user_id, reviewer_model in partial_match_cases:
            with self.subTest(
                partial_login=reviewer_login,
                reviewer_user_id=reviewer_user_id,
            ):
                changed = self._owner_envelope(
                    reviewer_login=reviewer_login,
                    reviewer_user_id=reviewer_user_id,
                    reviewer_model=reviewer_model,
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "partially match",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_owner_review_exact_head_tree_review_and_node_bindings_fail_closed(
        self,
    ) -> None:
        changed = self._owner_envelope()
        self._mutate_review(
            changed,
            lambda value: value.__setitem__("commit_id", "d" * 40),
        )
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "wrong head"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        self._replace_review_marker(changed, "reviewed tree", "d" * 40)
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "review body reviewed tree binding drift",
        ):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        changed["selected_review_id"] = REVIEW_ID + 1
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "selected review ID"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        changed["selected_review_node_id"] = REVIEW_NODE_ID + "_WRONG"
        with self.assertRaises(evidence.ReviewEvidenceError):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_owner_review_requires_exact_green_first_line_and_unique_markers(
        self,
    ) -> None:
        for first_line in ("", "GREEN — owner review"):
            with self.subTest(first_line=first_line or "missing"):
                changed = self._owner_envelope()

                def replace_first_line(body: str, value: str = first_line) -> str:
                    lines = body.splitlines()
                    self.assertEqual("GREEN", lines[0])
                    if value:
                        lines[0] = value
                    else:
                        lines.pop(0)
                    return "\n".join(lines)

                self._mutate_review_body(changed, replace_first_line)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "does not start with GREEN",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

        for label in REVIEW_MARKER_LABELS:
            with self.subTest(missing_marker=label):
                changed = self._owner_envelope()
                prefix = f"{label}: `"
                self._mutate_review_body(
                    changed,
                    lambda body, prefix=prefix: "\n".join(
                        line
                        for line in body.splitlines()
                        if not (line.startswith(prefix) and line.endswith("`"))
                    ),
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "exactly one .* marker",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

            with self.subTest(duplicate_marker=label):
                changed = self._owner_envelope()
                prefix = f"{label}: `"

                def duplicate_marker(body: str, prefix: str = prefix) -> str:
                    marker = next(
                        line
                        for line in body.splitlines()
                        if line.startswith(prefix) and line.endswith("`")
                    )
                    return body + "\n" + marker

                self._mutate_review_body(changed, duplicate_marker)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "exactly one .* marker",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

    def test_owner_review_bundle_and_reviewer_markers_are_exact(self) -> None:
        replacements = (
            ("target bundle", "f" * 64),
            ("immediate predecessor bundle", "e" * 64),
            (
                "reviewer model",
                evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN,
            ),
            ("reviewer login", "different-reviewer"),
            ("reviewer user ID", str(OWNER_USER_ID + 1)),
            ("reviewer author association", "MEMBER"),
            ("reviewer repository permission", "maintain"),
        )
        for label, replacement in replacements:
            with self.subTest(marker=label):
                changed = self._owner_envelope()
                self._replace_review_marker(changed, label, replacement)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "review body .* binding drift",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

        for section in ("reviewed_stage", "immediate_predecessor"):
            with self.subTest(bundle_object=section):
                changed = self._owner_envelope()
                changed[section]["bundle_sha256"] = "f" * 64
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "bundle digest drift",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

    def test_owner_review_cannot_claim_approval_independence_or_authority(
        self,
    ) -> None:
        forbidden = (
            ("github approval", "APPROVED"),
            ("third-party independence", "CLAIMED"),
            ("merge authority", "GRANTED"),
            ("AWS/IAM/OIDC/STS/S3 authority", "GRANTED"),
            (
                "workflow/release/activation/runtime/diagnostic authority",
                "GRANTED",
            ),
        )
        for label, replacement in forbidden:
            with self.subTest(marker=label):
                changed = self._owner_envelope()
                self._replace_review_marker(changed, label, replacement)
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "review body .* binding drift",
                ):
                    self.fixture.validate(
                        self.root,
                        raw=self.fixture.raw(changed),
                    )

        contradictory_prose = (
            (
                "This is an independent third-party review.",
                "cannot claim third-party independence",
            ),
            (
                "A third party independently performed this review.",
                "exact canonical machine-readable form",
            ),
            (
                "AWS runtime authority is hereby opened.",
                "exact canonical machine-readable form",
            ),
            (
                "This review authorizes IAM and S3 execution.",
                "exact canonical machine-readable form",
            ),
            (
                "Merge permission is granted.",
                "exact canonical machine-readable form",
            ),
        )
        for claim, message in contradictory_prose:
            with self.subTest(contradictory_prose=claim):
                changed = self._owner_envelope()
                self._mutate_review_body(
                    changed,
                    lambda body, claim=claim: body + "\n" + claim,
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    message,
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "unexpected reviewer model",
        ):
            self.fixture.validate(
                self.root,
                raw=self.fixture.raw(changed),
                expected_reviewer=evidence.ReviewerPolicy(
                    expected_login=OWNER_LOGIN,
                    expected_user_id=OWNER_USER_ID,
                    expected_model=(
                        evidence.DISTINCT_REPOSITORY_ASSOCIATED_COMMENTED_GREEN
                    ),
                ),
            )

    def test_review_chronology_and_later_red_supersession_fail_closed(self) -> None:
        changed = copy.deepcopy(self.fixture.envelope)
        self._mutate_source(
            changed,
            "reviewed_commit",
            lambda value: value["commit"]["committer"].__setitem__(
                "date",
                "2026-08-28T10:03:00Z",
            ),
        )
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "predates"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        wrapper = changed["source_payloads"]["review_pages"][0]
        page = _payload_value(wrapper)
        later_red = copy.deepcopy(page[0])
        later_red["id"] += 1
        later_red["node_id"] += "_RED"
        later_red["submitted_at"] = "2026-08-28T10:01:30Z"
        later_red["body"] = later_red["body"].replace("GREEN", "RED")
        page.append(later_red)
        _replace_payload(wrapper, page)
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "superseded"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        changed = self._owner_envelope()
        wrapper = changed["source_payloads"]["review_pages"][0]
        page = _payload_value(wrapper)
        later_red = copy.deepcopy(page[0])
        later_red["id"] += 2
        later_red["node_id"] += "_MARKERLESS_RED"
        later_red["submitted_at"] = "2026-08-28T10:01:30Z"
        later_red["body"] = "RED\n\nA later exact-head blocker without a gate marker."
        page.append(later_red)
        _replace_payload(wrapper, page)
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "superseded"):
            self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_historical_seed_identities_and_non_reuse_fields_are_exact(self) -> None:
        self.assertEqual(
            (
                "review_id",
                "review_node_id",
                "reviewed_head",
                "reviewed_tree",
            ),
            evidence.HISTORICAL_SEED_NON_REUSE_FIELDS,
        )
        self.assertEqual(
            (
                "review_id",
                "review_node_id",
                "evidence_sha256",
                "reviewed_head",
                "reviewed_tree",
            ),
            evidence.SCHEMA_1_1_GATE_NON_REUSE_FIELDS,
        )
        self.assertEqual(
            (
                (
                    "software",
                    5019067044,
                    "PRR_kwDOTw6wFs8AAAABKyjipA",
                    "443500de54917417276c39a635ae444458d03b0b",
                    "516d72a43545c454ef163e02ee1146005e6cfb5c",
                ),
                (
                    "g1",
                    5027672461,
                    "PRR_kwDOTw6wFs8AAAABK6wxjQ",
                    "4da7e67b600ef1ca10fb4f2e62b493d81d4dfcc3",
                    "b4c7b1524e8856450028e53be7912a88d3a675e1",
                ),
                (
                    "g2",
                    5033303996,
                    "PRR_kwDOTw6wFs8AAAABLAIfvA",
                    "63526d6c39c9225e647a18693c70ec8e73535ff4",
                    "eedeb4d6166c554b996ede740931c4bacb306f5d",
                ),
            ),
            tuple(
                (
                    seed.label,
                    seed.review_id,
                    seed.review_node_id,
                    seed.reviewed_head,
                    seed.reviewed_tree,
                )
                for seed in evidence.SEED_REVIEWS
            ),
        )
        self.assertNotIn("evidence_sha256", evidence.ReviewSeed.__dataclass_fields__)
        for field in evidence.HISTORICAL_SEED_NON_REUSE_FIELDS:
            with self.subTest(unique_seed_field=field):
                values = tuple(getattr(seed, field) for seed in evidence.SEED_REVIEWS)
                self.assertEqual(len(values), len(set(values)))

    def test_seed_and_cross_gate_review_reuse_fail_closed(self) -> None:
        owner = self._owner_envelope()
        owner_raw = self.fixture.raw(owner)
        owner_identity = self.fixture.validate(self.root, raw=owner_raw)
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "exact review-gate prefix"):
            self.fixture.validate(self.root, raw=owner_raw, consumed=())

        current_identity_values: tuple[tuple[str, object, str], ...] = (
            ("review_id", REVIEW_ID, "review ID reused"),
            ("review_node_id", REVIEW_NODE_ID, "review node ID reused"),
            (
                "evidence_sha256",
                hashlib.sha256(owner_raw).hexdigest(),
                "review evidence bytes reused",
            ),
            ("reviewed_head", HEAD, "reviewed head reused"),
            ("reviewed_tree", self.fixture.tree, "reviewed tree reused"),
        )
        for field, value, message in current_identity_values:
            with self.subTest(reused=field):
                reused_lineage = list(self.fixture.lineage)
                ancestor_index = -2 if field in {"reviewed_head", "reviewed_tree"} else -1
                reused_lineage[ancestor_index] = replace(
                    reused_lineage[ancestor_index],
                    **{field: value},
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    message,
                ):
                    self.fixture.validate(
                        self.root,
                        raw=owner_raw,
                        consumed=tuple(reused_lineage),
                    )

        ancestor_pair_values: tuple[tuple[str, str], ...] = (
            ("review_id", "review ID reused"),
            ("review_node_id", "review node ID reused"),
            ("evidence_sha256", "review evidence bytes reused"),
            ("reviewed_head", "reviewed head reused"),
            ("reviewed_tree", "reviewed tree reused"),
        )
        for field, message in ancestor_pair_values:
            with self.subTest(reused_between_ancestors=field):
                reused_lineage = list(self.fixture.lineage)
                reused_lineage[1] = replace(
                    reused_lineage[1],
                    **{field: getattr(reused_lineage[0], field)},
                )
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    message,
                ):
                    self.fixture.validate(
                        self.root,
                        raw=owner_raw,
                        consumed=tuple(reused_lineage),
                    )

        seed_messages = {
            "review_id": "seed review ID",
            "review_node_id": "seed review node ID",
            "reviewed_head": "seed reviewed head",
            "reviewed_tree": "seed reviewed tree",
        }
        for seed in evidence.SEED_REVIEWS:
            for field in evidence.HISTORICAL_SEED_NON_REUSE_FIELDS:
                with self.subTest(seed=seed.label, seed_reused_by_ancestor=field):
                    reused_lineage = list(self.fixture.lineage)
                    reused_lineage[0] = replace(
                        reused_lineage[0],
                        **{field: getattr(seed, field)},
                    )
                    with self.assertRaisesRegex(
                        evidence.ReviewEvidenceError,
                        seed_messages[field],
                    ):
                        evidence._validate_reuse(
                            owner_identity,
                            tuple(reused_lineage),
                        )

            changed = copy.deepcopy(owner)
            changed["selected_review_id"] = seed.review_id
            self._mutate_review(
                changed,
                lambda value, seed=seed: value.__setitem__(
                    "id",
                    seed.review_id,
                ),
            )
            with self.subTest(seed=seed.label, candidate_reuses="review_id"):
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "seed review ID",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

            changed = copy.deepcopy(owner)
            changed["selected_review_node_id"] = seed.review_node_id
            self._mutate_review(
                changed,
                lambda value, seed=seed: value.__setitem__(
                    "node_id",
                    seed.review_node_id,
                ),
            )
            with self.subTest(seed=seed.label, candidate_reuses="review_node_id"):
                with self.assertRaisesRegex(
                    evidence.ReviewEvidenceError,
                    "seed review node ID",
                ):
                    self.fixture.validate(self.root, raw=self.fixture.raw(changed))

            for field in ("reviewed_head", "reviewed_tree"):
                with self.subTest(seed=seed.label, candidate_reuses=field):
                    with self.assertRaisesRegex(
                        evidence.ReviewEvidenceError,
                        seed_messages[field],
                    ):
                        evidence._validate_reuse(
                            replace(
                                owner_identity,
                                **{field: getattr(seed, field)},
                            ),
                            self.fixture.lineage,
                        )

        shrunken_predecessor = list(self.fixture.lineage)
        shrunken_predecessor[-1] = replace(
            shrunken_predecessor[-1],
            target_bundle_sha256="f" * 64,
        )
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "does not equal the prior reviewed target",
        ):
            self.fixture.validate(
                self.root,
                raw=owner_raw,
                consumed=tuple(shrunken_predecessor),
            )

    def test_envelope_hash_binding_and_reviewed_blob_binding_fail_closed(self) -> None:
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "binding drift"):
            self.fixture.validate(self.root, expected_sha="0" * 64)

        def wrong_reader(head: str, relative: str) -> bytes:
            raw = self.fixture.reader(head, relative)
            return raw + b"tampered"

        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "blob SHA-256 mismatch"):
            self.fixture.validate(self.root, reader=wrong_reader)

        changed_files = dict(self.fixture.target_files)
        changed_files[next(iter(changed_files))] = "f" * 64
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "file set or digest drift"):
            self.fixture.validate(self.root, target_files=changed_files)

        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "case-fold-colliding"):
            evidence.bundle_sha256(
                {
                    "governance/Stage.json": "1" * 64,
                    "governance/stage.json": "2" * 64,
                }
            )

    def test_self_contained_tree_blob_and_immediate_predecessor_bindings_fail_closed(self) -> None:
        self.assertFalse((self.root / ".git").exists())
        self.fixture.validate(self.root)

        with self.subTest("wrong immediate PR base"):
            changed = copy.deepcopy(self.fixture.envelope)
            self._mutate_source(
                changed,
                "pull_request",
                lambda value: value["base"].__setitem__("sha", "f" * 40),
            )
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "base skips"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        with self.subTest("truncated recursive tree"):
            changed = copy.deepcopy(self.fixture.envelope)
            self._mutate_source(
                changed,
                "reviewed_tree",
                lambda value: value.__setitem__("truncated", True),
            )
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "is truncated"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        with self.subTest("Git blob framing mismatch"):
            changed = copy.deepcopy(self.fixture.envelope)
            relative = next(iter(self.fixture.target_blobs))
            wrapper = changed["source_payloads"]["target_blobs"][relative]
            value = _payload_value(wrapper)
            raw = base64.b64decode(value["content"])
            value["content"] = base64.b64encode(bytes([raw[0] ^ 1]) + raw[1:]).decode("ascii")
            _replace_payload(wrapper, value)
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "Git blob OID mismatch"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

        with self.subTest("predecessor mutated in reviewed tree"):
            changed = copy.deepcopy(self.fixture.envelope)
            wrapper = changed["source_payloads"]["reviewed_tree"]
            value = _payload_value(wrapper)
            predecessor_path = next(iter(self.fixture.predecessor_blobs))
            entry = next(item for item in value["tree"] if item["path"] == predecessor_path)
            entry["sha"] = "f" * 40
            entry["url"] = (
                "https://api.github.com/repos/"
                f"{evidence.REPOSITORY_FULL_NAME}/git/blobs/" + "f" * 40
            )
            _replace_payload(wrapper, value)
            with self.assertRaisesRegex(evidence.ReviewEvidenceError, "Git tree object ID mismatch"):
                self.fixture.validate(self.root, raw=self.fixture.raw(changed))

    def test_reviewed_stage_subject_cannot_preexist_its_review_transition(self) -> None:
        changed = copy.deepcopy(self.fixture.envelope)
        subject_path = evidence.GATE_REGISTRY[GATE_ID].subject_paths[0]
        predecessor_tree, predecessor_payload, _ = _tree_capture(
            {
                **self.fixture.predecessor_tree_inputs,
                subject_path: self.fixture.target_blobs[subject_path],
            }
        )
        changed["source_payloads"]["predecessor_tree"] = predecessor_payload
        changed["immediate_predecessor"]["reviewed_tree"] = predecessor_tree
        wrapper = changed["source_payloads"]["review_pages"][0]
        page = _payload_value(wrapper)
        page[0]["body"] = page[0]["body"].replace(
            f"immediate predecessor tree: `{self.fixture.predecessor_tree}`",
            f"immediate predecessor tree: `{predecessor_tree}`",
        )
        _replace_payload(wrapper, page)
        lineage = (
            *self.fixture.lineage[:-1],
            replace(self.fixture.lineage[-1], reviewed_tree=predecessor_tree),
        )
        with self.assertRaisesRegex(
            evidence.ReviewEvidenceError,
            "predates its mandatory review transition",
        ):
            self.fixture.validate(
                self.root,
                raw=self.fixture.raw(changed),
                consumed=lineage,
            )

    def test_evidence_cannot_review_itself_and_absence_gate_rejects_any_entry(self) -> None:
        self.fixture.write(self.root)
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "must be absent"):
            evidence.require_no_review_evidence(self.root)

        files = dict(self.fixture.target_files)
        files[evidence.evidence_path(GATE_ID)] = "e" * 64
        with self.assertRaisesRegex(evidence.ReviewEvidenceError, "cannot review itself"):
            self.fixture.validate(self.root, target_files=files)


if __name__ == "__main__":
    unittest.main()
