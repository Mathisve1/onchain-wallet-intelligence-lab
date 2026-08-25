#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, ROUND_CEILING, getcontext
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

GREEN_HEAD = "443500de54917417276c39a635ae444458d03b0b"
GREEN_TREE = "516d72a43545c454ef163e02ee1146005e6cfb5c"
GREEN_REVIEW = 5019067044
BASE_SHA = "1d218755ead2cbf635ca0e1741f53e0184c0e239"
AMENDMENT_SHA = "bdd610c678189e8098381d8c4a0fd12296bf2e0cd8e9ec0fed375b073872552f"
BINDINGS_SHA = "f60f7d6eac5f5a4633a5453c1c79bd84a54add69d1395d9048658450211bd0ba"
SELECTION_SHA = "7c134f4b62f547904126a5f810c177484dceeffa246d53c5c35944367d563eb2"
PRIOR_RESULT_SHA = "9d3266eb53791d83df29b6ec3ae5f33c254b29a8182f2e6be7e3261c02686862"
JOINED_ROWS_SHA = "1d9e41c058471f85e6478565034320727137f210383d5a3f23eb1531d14b4970"
GREEN_CONTRACT_SHA = "0cf3515c3af12401e3c8381b180ed9122fdf0923979a156891e5e8e22308cddd"
GREEN_STATUS_SHA = "855a052b22e0b471eb0433205f71b227b5c8baeb7c70cd4d8a563f8007462c6b"
PENDING_RUNTIME_PRICING_SHA = "5e5a6469b921a15cbac1e2f03184e2dfcf6ffee51dc2e86833e9556a5c23c226"
PERMISSION_SHA = "2769afe520efff6f0b619fff352d2cf13d412d96d6c4642fcfc61a8165787e6a"
TRUST_SHA = "375e224b269a62873afb4516651a259483feed4f211e9184272cb2af91513668"
ROLE_DECISION_SHA = "20f9895c83c1d61c79640ed551afd2458fa276502bf3eb9e7f8f3aa040d83d8f"
DEPENDENCIES_SHA = "ce9387377db1f372c6425849549c25e2e47bf24e336510bca06892661e045d6a"
FEASIBILITY_SHA = "fa71f17591caa0cf939c163733b6f2d87835a06b2f223421b6a6c07cb8d76efb"
WORKFLOW_SHA = "c10b810304d6cdbc68f23cb3db113b57580d34f0f74e781aefa2140edd0b5e65"
ENVELOPE_SHA = "89631f04394805bdf80be0a3784b1cc174eb0fe20e0627bc4eff63cc5f649b2e"
PRICING_SHA = "3459dbfe25d2e7244823344312de5025b7064928c6f436fbe751c7299ea41574"
RUNTIME_PRICING_CANDIDATE_SHA = "d5043062386b3d70f695f09c917f11719512918c56f318cace1e0530b709ac43"
STATEMENT_SHA = "16f9f2c31ff90952033251d917884b1ca55771511e82e4b813414dc1a3f807d3"
PACKAGE_SHA = "a31c09cb73b3c176c360a8218aa1eae2faf6e02772b2ca1ff35cfd0babedb24f"

AMENDMENT = "research/archive_inventory/r11a_v2/R11A_CORRECTIVE_PREREGISTRATION_AMENDMENT.json"
BINDINGS = "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"
SELECTION = "research/archive_inventory/r11/R11_72H_SELECTION.json"
PRIOR_RESULT = "research/archive_inventory/r11_evidence/run-31436753081/r11-result.json"
CONTRACT = "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_IMPLEMENTATION_CONTRACT_R7.json"
R7_STATUS = "research/archive_inventory/r11a_corrective/R11A_CORRECTIVE_STATUS_R7.json"
PENDING_PRICING = "research/archive_inventory/r11a_corrective/R11A_PRICING_EUR_SNAPSHOT.json"
PERMISSION = "research/archive_inventory/r11a_corrective/R11A_PERMISSION_POLICY.json"
TRUST = "research/archive_inventory/r11a_corrective/R11A_OIDC_TRUST_POLICY.json"
ROLE_DECISION = "research/archive_inventory/r11a_corrective/R11A_ROLE_DECISION.json"
DEPENDENCIES = "research/archive_inventory/r11a_corrective/R11A_DEPENDENCIES.json"
FEASIBILITY = "research/archive_inventory/r11a_corrective/R11A_RESOURCE_FEASIBILITY_R3.json"
WORKFLOW = "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r7.yml"
ENVELOPE = "research/archive_inventory/r11a_g1/R11A_G1_EXECUTION_ENVELOPE.json"
PRICING = "research/archive_inventory/r11a_g1/R11A_G1_PRICING_EUR_BINDING.json"
RUNTIME_PRICING_CANDIDATE = "research/archive_inventory/r11a_g1/R11A_G1_RUNTIME_PRICING_SNAPSHOT_CANDIDATE.json"
STATEMENT = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_STATEMENT.txt"
PACKAGE = "research/archive_inventory/r11a_g1/R11A_G1_OWNER_APPROVAL_PACKAGE.json"
STATUS = "research/archive_inventory/r11a_g1/R11A_G1_STATUS.json"

# A = independently derived/recomputed; B = projected from an exact-byte-bound
# authoritative source; C = fixed governance literal checked exactly; D =
# proven immaterial informational data.  Every scalar status field is assigned
# individually, and this registry is checked against the constructed schema.
STATUS_FIELD_CLASSIFICATION = {
    ("schema_version",): "C",
    ("status_id",): "C",
    ("status",): "C",
    ("decision",): "C",
    ("repository",): "C",
    ("software_anchor", "review_id"): "B",
    ("software_anchor", "review_event"): "B",
    ("software_anchor", "review_verdict"): "B",
    ("software_anchor", "reviewed_head"): "B",
    ("software_anchor", "reviewed_tree"): "C",
    ("software_anchor", "base_sha"): "B",
    ("software_anchor", "sha_drift"): "A",
    ("software_anchor", "superseding_red_review_present"): "B",
    ("software_anchor", "verified_against_live_github_on_date_utc"): "C",
    ("historical_r7_seal", "semantics"): "C",
    ("historical_r7_seal", "reviewed_head_contract_sha256"): "B",
    ("historical_r7_seal", "reviewed_head_status_sha256"): "B",
    ("historical_r7_seal", "historical_semantics_rewritten"): "C",
    (
        "historical_r7_seal",
        "successor_manifest_projection_may_be_mechanically_resealed",
    ): "C",
    ("current_bindings", "execution_envelope_path"): "C",
    ("current_bindings", "execution_envelope_sha256"): "B",
    ("current_bindings", "pricing_eur_binding_path"): "C",
    ("current_bindings", "pricing_eur_binding_sha256"): "B",
    ("current_bindings", "runtime_pricing_candidate_path"): "C",
    ("current_bindings", "runtime_pricing_candidate_sha256"): "B",
    ("current_bindings", "owner_approval_package_path"): "C",
    ("current_bindings", "owner_approval_package_sha256"): "B",
    ("current_bindings", "proposed_owner_statement_path"): "C",
    ("current_bindings", "proposed_owner_statement_sha256"): "B",
    ("pricing", "current_official_binding"): "A",
    ("pricing", "pricing_binding_pending"): "B",
    ("pricing", "raw_max_eur_ceil_6dp"): "A",
    ("pricing", "projected_with_contingency_eur_ceil_6dp"): "A",
    ("pricing", "owner_approval_max_eur"): "B",
    ("pricing", "monthly_recurring_budget_eur"): "B",
    ("iam_workflow_readiness", "status"): "A",
    (
        "iam_workflow_readiness",
        "permission_policy_exact_72_getobject_resources",
    ): "A",
    (
        "iam_workflow_readiness",
        "oidc_repository_owner_ref_and_workflow_restricted",
    ): "A",
    ("iam_workflow_readiness", "workflow_exact_hash_bound"): "A",
    ("iam_workflow_readiness", "workflow_candidate_outside_dot_github"): "A",
    ("iam_workflow_readiness", "secrets_or_reusable_credentials"): "A",
    ("iam_workflow_readiness", "external_infrastructure_created"): "A",
    ("owner_approval", "approval_id"): "B",
    ("owner_approval", "approval_status"): "B",
    ("owner_approval", "owner_approval_ready"): "A",
    ("owner_approval", "owner_approval_present"): "A",
    ("owner_approval", "canonical_approval_record_present"): "A",
    ("runtime_authority", "successor_role_created"): "A",
    ("runtime_authority", "aws_iam_mutation"): "A",
    ("runtime_authority", "aws_oidc"): "A",
    ("runtime_authority", "sts"): "A",
    ("runtime_authority", "workflow_installed"): "A",
    ("runtime_authority", "runtime_binding_present"): "A",
    ("runtime_authority", "runtime_release"): "A",
    ("runtime_authority", "runtime_activation"): "A",
    ("runtime_authority", "requester_pays"): "A",
    ("runtime_authority", "get_object"): "A",
    ("runtime_authority", "object_body_download"): "A",
    ("runtime_authority", "decompression"): "A",
    ("runtime_authority", "diagnostic_execution"): "A",
    ("runtime_authority", "diagnostic_artifact_retention"): "A",
    ("science_state", "empirical_root_cause"): "B",
    ("science_state", "deduplication"): "A",
    ("science_state", "replay_suppression"): "A",
    ("science_state", "r11b_repair"): "A",
    ("science_state", "wallet_ranking"): "A",
    ("science_state", "copyability"): "A",
    ("science_state", "r11_closed"): "A",
    ("science_state", "r12_ready"): "A",
    ("trading_authorizations", "integration"): "A",
    ("trading_authorizations", "paper"): "A",
    ("trading_authorizations", "shadow"): "A",
    ("trading_authorizations", "live"): "A",
    ("trading_authorizations", "leverage"): "A",
    ("trading_authorizations", "capital_allocation"): "A",
}
STATUS_INFORMATIONAL_FIELDS: frozenset[tuple[str, ...]] = frozenset()


class G1ReadinessError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise G1ReadinessError(message)


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise G1ReadinessError(f"non-finite JSON constant: {value}")


def load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    require(path.is_file(), f"required file absent: {relative}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise G1ReadinessError(f"invalid strict JSON: {relative}") from exc
    require(isinstance(value, dict), f"JSON root is not object: {relative}")
    return value


def sha256(root: Path, relative: str) -> str:
    path = root / relative
    require(path.is_file(), f"hash target absent: {relative}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_all_false(value: object, label: str) -> None:
    require(isinstance(value, dict) and value, f"{label} must be nonempty object")
    require(all(observed is False for observed in value.values()), f"{label} opens authority")


def require_exact(observed: object, expected: object, label: str) -> None:
    require(type(observed) is type(expected), f"{label} type mismatch")
    if type(expected) is dict:
        observed_dict = observed
        expected_dict = expected
        require(
            set(observed_dict) == set(expected_dict),
            f"{label} key set mismatch",
        )
        for key, expected_value in expected_dict.items():
            require_exact(observed_dict[key], expected_value, f"{label}.{key}")
        return
    if type(expected) is list:
        observed_list = observed
        expected_list = expected
        require(len(observed_list) == len(expected_list), f"{label} length mismatch")
        for index, expected_value in enumerate(expected_list):
            require_exact(observed_list[index], expected_value, f"{label}[{index}]")
        return
    require(observed == expected, f"{label} value mismatch")


def scalar_leaf_paths(
    value: object,
    prefix: tuple[str, ...] = (),
) -> set[tuple[str, ...]]:
    if type(value) is dict:
        paths: set[tuple[str, ...]] = set()
        for key, nested_value in value.items():
            paths.update(scalar_leaf_paths(nested_value, prefix + (key,)))
        return paths
    if type(value) is list:
        paths = set()
        for index, nested_value in enumerate(value):
            paths.update(scalar_leaf_paths(nested_value, prefix + (str(index),)))
        return paths
    return {prefix}


def canonical_joined_rows(selection: dict[str, Any], prior: dict[str, Any]) -> list[dict[str, Any]]:
    targets = selection.get("exact_targets")
    summaries = prior.get("per_hour_summaries")
    require(isinstance(targets, list) and len(targets) == 72, "selection is not exact 72")
    require(isinstance(summaries, list) and len(summaries) == 72, "prior result is not exact 72")
    summary_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for summary in summaries:
        require(isinstance(summary, dict), "prior per-hour row is not object")
        identity = (summary.get("object_key"), summary.get("path_hour_utc"))
        require(all(isinstance(item, str) for item in identity), "prior row identity malformed")
        require(identity not in summary_by_identity, "duplicate prior row identity")
        summary_by_identity[identity] = summary
    rows: list[dict[str, Any]] = []
    for ordinal, target in enumerate(targets):
        require(isinstance(target, dict), "selection target is not object")
        key = target.get("key")
        hour = target.get("path_hour_utc")
        require(isinstance(key, str) and isinstance(hour, str), "selection identity malformed")
        summary = summary_by_identity.get((key, hour))
        require(isinstance(summary, dict), "selection target absent from prior result")
        require(target.get("expected_etag") == summary.get("expected_etag"), "ETag join drift")
        require(
            target.get("expected_size_bytes")
            == summary.get("expected_content_length")
            == summary.get("observed_content_length"),
            "content-length join drift",
        )
        digest = summary.get("compressed_sha256")
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "compressed SHA malformed")
        rows.append(
            {
                "ordinal_zero_based": ordinal,
                "object_key": key,
                "path_hour_utc": hour,
                "expected_etag": target["expected_etag"],
                "expected_size_bytes": target["expected_size_bytes"],
                "storage_class": target["storage_class"],
                "compressed_sha256": digest,
            }
        )
    require(len(summary_by_identity) == len(rows), "prior result has unjoined row")
    return rows


def joined_rows_sha256(rows: list[dict[str, Any]]) -> str:
    raw = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ceil_six(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING), "f")


def validate(root: Path = ROOT) -> None:
    root = root.resolve()
    expected_hashes = {
        AMENDMENT: AMENDMENT_SHA,
        BINDINGS: BINDINGS_SHA,
        SELECTION: SELECTION_SHA,
        PRIOR_RESULT: PRIOR_RESULT_SHA,
        R7_STATUS: GREEN_STATUS_SHA,
        PENDING_PRICING: PENDING_RUNTIME_PRICING_SHA,
        PERMISSION: PERMISSION_SHA,
        TRUST: TRUST_SHA,
        ROLE_DECISION: ROLE_DECISION_SHA,
        DEPENDENCIES: DEPENDENCIES_SHA,
        FEASIBILITY: FEASIBILITY_SHA,
        WORKFLOW: WORKFLOW_SHA,
        ENVELOPE: ENVELOPE_SHA,
        PRICING: PRICING_SHA,
        RUNTIME_PRICING_CANDIDATE: RUNTIME_PRICING_CANDIDATE_SHA,
        STATEMENT: STATEMENT_SHA,
        PACKAGE: PACKAGE_SHA,
    }
    for relative, expected in expected_hashes.items():
        require(sha256(root, relative) == expected, f"bound file hash drift: {relative}")

    amendment = load(root, AMENDMENT)
    require(amendment.get("amendment_id") == "R11A-CORRECTIVE-PREREGISTRATION-AMENDMENT-002", "Amendment ID drift")
    require(amendment.get("diagnostic_id") == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-002", "diagnostic ID drift")
    require(amendment.get("status") == "PREREGISTERED_NO_EXECUTION", "Amendment opens execution")
    require(amendment.get("owner_approval_eligible_now") is False, "historical Amendment claims approval eligibility")

    bindings = load(root, BINDINGS)
    require(bindings.get("status") == "SEALED_PREREGISTRATION_NO_EXECUTION", "V2 bindings status drift")
    require(bindings.get("file_sha256", {}).get(AMENDMENT) == AMENDMENT_SHA, "V2 binding does not seal Amendment")

    selection = load(root, SELECTION)
    prior = load(root, PRIOR_RESULT)
    rows = canonical_joined_rows(selection, prior)
    require(joined_rows_sha256(rows) == JOINED_ROWS_SHA, "72-object joined identity digest drift")
    require(sum(row["expected_size_bytes"] for row in rows) == 2107738436, "compressed byte sum drift")
    expected_keys = {
        f"node_fills_by_block/hourly/{day}/{hour}.lz4"
        for day in ("20250728", "20250729", "20250730")
        for hour in range(24)
    }
    require({row["object_key"] for row in rows} == expected_keys, "object set is not exact 72-hour scope")
    require(all(row["storage_class"] == "STANDARD" for row in rows), "non-STANDARD object entered scope")

    envelope = load(root, ENVELOPE)
    require(envelope.get("status") == "FROZEN_INERT_NO_EXECUTION", "envelope opens execution")
    require(envelope.get("software_anchor") == {
        "reviewed_head": GREEN_HEAD,
        "authoritative_review_id": GREEN_REVIEW,
        "review_event": "COMMENTED",
        "review_verdict": "GREEN",
    }, "software anchor drift")
    identity = envelope.get("object_identity_binding", {})
    require(identity.get("selected_object_count") == 72, "envelope object count drift")
    require(identity.get("canonical_joined_rows_sha256") == JOINED_ROWS_SHA, "envelope object digest drift")
    scope = envelope.get("scope", {})
    require(scope.get("bucket") == "hl-mainnet-node-data" and scope.get("region") == "ap-northeast-1", "bucket or Region drift")
    require(scope.get("seventy_third_object_authorized") is False, "73rd object authorized")
    require(scope.get("other_historical_window_authorized") is False, "historical expansion authorized")
    network = envelope.get("network_envelope", {})
    require(network.get("allowed_s3_operation") == "s3:GetObject", "S3 operation drift")
    require(network.get("maximum_s3_get_object_requests") == 72, "request cap drift")
    require(network.get("maximum_requests_per_object") == 1, "per-object request cap drift")
    require(network.get("maximum_retries_per_request") == 0, "retry cap drift")
    for key in (
        "http_redirect_following_authorized",
        "pagination_authorized",
        "head_object_authorized",
        "range_get_authorized",
        "list_objects_v2_authorized",
        "list_object_versions_authorized",
        "list_all_my_buckets_authorized",
        "get_object_attributes_authorized",
        "get_object_version_authorized",
        "put_delete_restore_or_multipart_authorized",
    ):
        require(network.get(key) is False, f"forbidden network authority opened: {key}")
    resources = envelope.get("resource_envelope", {})
    required_resource_values = {
        "maximum_total_compressed_bytes": 2107738436,
        "maximum_downloaded_bytes": 2107738436,
        "maximum_ephemeral_workspace_bytes": 5368709120,
        "maximum_retained_artifact_bytes": 134217728,
        "maximum_runtime_seconds": 21600,
    }
    require(all(resources.get(key) == value for key, value in required_resource_values.items()), "resource envelope drift")
    terminal = envelope.get("terminal_classes")
    expected_terminal = [
        {
            "priority": 1,
            "return_code": 21,
            "terminal_class": "R11A_V2_ARTIFACT_CAP_EXCEEDED",
            "scientific_output_status": "EMPTY",
            "root_cause_claim_status": "NOT_PROVEN",
        },
        {
            "priority": 2,
            "return_code": 0,
            "terminal_class": "R11A_V2_ROOT_CAUSE_TAXONOMY_COMPLETE",
            "scientific_output_status": "COMPLETE",
            "root_cause_claim_status": "PROVEN_COMPLETE_TAXONOMY_ONLY",
        },
        {
            "priority": 3,
            "return_code": 20,
            "terminal_class": "R11A_V2_DIAGNOSTIC_INCOMPLETE",
            "scientific_output_status": "COMPLETE",
            "root_cause_claim_status": "NOT_PROVEN",
        },
        {
            "priority": 4,
            "return_code": 21,
            "terminal_class": "R11A_V2_FAIL_CLOSED_EARLY_STOP",
            "scientific_output_status": "EMPTY",
            "root_cause_claim_status": "NOT_PROVEN",
        },
    ]
    require(terminal == expected_terminal, "exact terminal class mapping drift")
    require_all_false(envelope.get("prohibited_scientific_scope"), "envelope scientific scope")
    require_all_false(envelope.get("authority_state"), "envelope authority")

    permission = load(root, PERMISSION)
    statements = permission.get("Statement")
    require(isinstance(statements, list) and len(statements) == 3, "permission statement set drift")
    allow = [row for row in statements if isinstance(row, dict) and row.get("Effect") == "Allow"]
    require(len(allow) == 1 and allow[0].get("Action") == "s3:GetObject", "permission Allow drift")
    resources_allowed = allow[0].get("Resource")
    require(isinstance(resources_allowed, list) and len(resources_allowed) == 72, "permission resources not exact 72")
    expected_arns = {f"arn:aws:s3:::hl-mainnet-node-data/{key}" for key in expected_keys}
    require(set(resources_allowed) == expected_arns, "permission policy differs from frozen objects")
    denied_actions = {
        action
        for row in statements
        if isinstance(row, dict) and row.get("Effect") == "Deny"
        for action in (row.get("Action") if isinstance(row.get("Action"), list) else [])
    }
    require({"s3:ListBucket", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectVersion"}.issubset(denied_actions), "least-privilege deny set drift")

    trust = load(root, TRUST)
    trust_statements = trust.get("Statement")
    require(isinstance(trust_statements, list) and len(trust_statements) == 1, "trust statement drift")
    condition = trust_statements[0].get("Condition", {}).get("StringEquals", {})
    expected_condition = {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:Mathisve1@163474992/onchain-wallet-intelligence-lab@1326362646:ref:refs/heads/main",
        "token.actions.githubusercontent.com:repository_id": "1326362646",
        "token.actions.githubusercontent.com:repository_owner_id": "163474992",
        "token.actions.githubusercontent.com:ref": "refs/heads/main",
        "token.actions.githubusercontent.com:workflow": "Hyperliquid Archive R11A Identity Boundary Diagnostic",
    }
    require(condition == expected_condition, "OIDC trust restriction drift")

    role = load(root, ROLE_DECISION)
    successor_role = role.get("successor_role", {})
    require(successor_role.get("role_arn") == "arn:aws:iam::630956766927:role/onchain-wallet-intelligence-hl-archive-identity-r11a", "role ARN drift")
    require(successor_role.get("maximum_session_duration_seconds") == 21600, "session duration drift")
    require(successor_role.get("persistent_get_object_resource_count") == 72, "role resource count drift")
    require(role.get("new_role_created_by_this_decision") is False, "role already created")
    require(role.get("current_authority") and all(value is False for value in role["current_authority"].values()), "role decision opens authority")

    workflow_text = (root / WORKFLOW).read_text(encoding="utf-8")
    for token in (
        "on:\n  workflow_dispatch:",
        "contents: read",
        "actions: read",
        "id-token: write",
        "retry-max-attempts: 1",
        "test \"${DISPATCH_REF}\" = refs/heads/main",
        "test \"${CURRENT_RUN_ATTEMPT}\" = 1",
    ):
        require(token in workflow_text, f"workflow least-privilege token absent: {token}")
    require("secrets." not in workflow_text, "workflow references secret")
    require("s3:PutObject" not in workflow_text and "s3:DeleteObject" not in workflow_text, "workflow opens S3 mutation")
    installed_workflow = root / ".github/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml"
    require(not installed_workflow.exists(), "runtime workflow is installed")

    pending = load(root, PENDING_PRICING)
    require(pending.get("status") == "AWAITING_CURRENT_OFFICIAL_BINDING_BEFORE_OWNER_APPROVAL", "historical pending pricing snapshot was rewritten")

    pricing = load(root, PRICING)
    require(pricing.get("status") == "PASS_CURRENT_OFFICIAL_PRICING_BOUND_NO_EXECUTION", "G1 pricing binding not PASS")
    require(pricing.get("pricing_binding_pending") is False, "G1 pricing remains pending")
    sources = pricing.get("pricing_sources")
    require(isinstance(sources, list) and len(sources) == 2, "both AWS price sources are required")
    require([row.get("sha256") for row in sources] == [
        "8c2d57d8c2fe01c026a7c7c7796d25535d54e0004460b55b50ac8e48d9c3011e",
        "0cdc27bd57f32449ed94bc2cefab87b69c49882c4f52e541b984affe65f83dcf",
    ], "AWS source digest drift")
    fx_sources = pricing.get("fx_sources")
    require(isinstance(fx_sources, list) and len(fx_sources) == 2, "ECB evidence pair absent")
    require(fx_sources[0].get("reference_date") == "2026-08-24" and fx_sources[0].get("usd_per_eur") == "1.1664", "ECB binding drift")

    getcontext().prec = 60
    request_usd = Decimal(72) * Decimal("0.0037") / Decimal(10000)
    transfer_gib = Decimal(2107738436) / Decimal(1073741824)
    transfer_usd = transfer_gib * Decimal("0.114")
    total_usd = request_usd + transfer_usd
    request_eur = request_usd / Decimal("1.1664")
    transfer_eur = transfer_usd / Decimal("1.1664")
    total_eur = total_usd / Decimal("1.1664")
    projected_eur = total_eur * Decimal("2.0")
    calculation = pricing.get("calculation", {})
    require(Decimal(calculation.get("aws_request_cost_usd")) == request_usd, "request cost math drift")
    require(Decimal(calculation.get("transfer_gib")) == transfer_gib, "transfer unit math drift")
    require(Decimal(calculation.get("aws_transfer_cost_usd")) == transfer_usd, "transfer cost math drift")
    require(Decimal(calculation.get("total_raw_max_usd")) == total_usd, "USD total math drift")
    require(Decimal(calculation.get("total_raw_max_eur_exact")) == total_eur, "EUR total math drift")
    require(calculation.get("aws_request_cost_eur_ceil_6dp") == ceil_six(request_eur), "request EUR rounding drift")
    require(calculation.get("aws_transfer_cost_eur_ceil_6dp") == ceil_six(transfer_eur), "transfer EUR rounding drift")
    require(calculation.get("total_raw_max_eur_ceil_6dp") == ceil_six(total_eur), "raw EUR rounding drift")
    require(calculation.get("projected_with_contingency_eur_ceil_6dp") == ceil_six(projected_eur), "contingency math drift")
    require(calculation.get("owner_approval_max_eur_micros") == 500000, "approval ceiling drift")
    require(calculation.get("monthly_recurring_budget_eur_micros") == 0, "recurring budget opened")

    runtime_pricing = load(root, RUNTIME_PRICING_CANDIDATE)
    require(runtime_pricing.get("status") == "BOUND_CURRENT_OFFICIAL_SNAPSHOT", "runtime pricing candidate not bound")
    require(runtime_pricing.get("candidate_status") == "INERT_NOT_INSTALLED_NOT_RUNTIME_AUTHORITY", "runtime pricing candidate activated")
    require(runtime_pricing.get("snapshot_sha256") == PRICING_SHA, "runtime candidate does not bind comprehensive pricing")
    candidate_projected = (
        (Decimal(72) * Decimal(str(runtime_pricing["get_request_usd_per_1000"])) / Decimal(1000))
        + (Decimal(2107738436) / Decimal(1073741824)) * Decimal(str(runtime_pricing["data_transfer_out_usd_per_gib"]))
    ) / Decimal(str(runtime_pricing["usd_per_eur"])) * Decimal(str(runtime_pricing["contingency_multiplier"]))
    candidate_micros = int((candidate_projected * Decimal(1000000)).to_integral_value(rounding=ROUND_CEILING))
    require(candidate_micros == 383757 == runtime_pricing.get("projected_eur_micros_at_frozen_maximum"), "runtime pricing projection drift")
    require(runtime_pricing.get("installed_at_runtime_snapshot_path") is False, "runtime pricing candidate installed")

    package = load(root, PACKAGE)
    require(package.get("package_id") == "R11A-G1-OWNER-APPROVAL-PACKAGE-001", "package ID drift")
    require(package.get("proposed_approval_id") == "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001", "approval ID drift")
    require(package.get("approval_status") == "AWAITING_EXPLICIT_OWNER_APPROVAL", "approval package status drift")
    require(package.get("owner_approval_present") is False, "owner approval falsely present")
    anchor = package.get("software_anchor", {})
    require(anchor.get("reviewed_head") == GREEN_HEAD and anchor.get("authoritative_review_id") == GREEN_REVIEW, "package GREEN anchor drift")
    require(anchor.get("reviewed_head_contract_sha256") == GREEN_CONTRACT_SHA, "reviewed contract anchor drift")
    bound_files = package.get("bound_files")
    require(isinstance(bound_files, dict), "package bound_files absent")
    expected_package_bound = {
        AMENDMENT: AMENDMENT_SHA,
        BINDINGS: BINDINGS_SHA,
        SELECTION: SELECTION_SHA,
        PRIOR_RESULT: PRIOR_RESULT_SHA,
        PERMISSION: PERMISSION_SHA,
        TRUST: TRUST_SHA,
        ROLE_DECISION: ROLE_DECISION_SHA,
        DEPENDENCIES: DEPENDENCIES_SHA,
        FEASIBILITY: FEASIBILITY_SHA,
        WORKFLOW: WORKFLOW_SHA,
        ENVELOPE: ENVELOPE_SHA,
        PRICING: PRICING_SHA,
        RUNTIME_PRICING_CANDIDATE: RUNTIME_PRICING_CANDIDATE_SHA,
        STATEMENT: STATEMENT_SHA,
    }
    require(bound_files == expected_package_bound, "approval package file binding drift")
    require(package.get("canonical_approval_record", {}).get("present_now") is False, "package claims canonical approval")
    require(package.get("frozen_authority_if_explicitly_approved", {}).get("data_execution_authorized_by_approval_alone") is False, "approval package self-releases execution")
    require_all_false(package.get("not_authorized"), "package prohibited authority")
    require_all_false(package.get("runtime_state"), "package runtime state")
    require(package.get("science_state", {}).get("r11_closed") is False, "package closes R11")
    require(package.get("science_state", {}).get("r12_ready") is False, "package opens R12")

    candidate_identity = package.get("candidate_identity")
    package_runtime = package.get("runtime_state")
    package_science = package.get("science_state")
    not_authorized = package.get("not_authorized")
    require(isinstance(candidate_identity, dict), "package candidate identity absent")
    require(isinstance(package_runtime, dict), "package runtime state absent")
    require(isinstance(package_science, dict), "package science state absent")
    require(isinstance(not_authorized, dict), "package prohibited authority absent")

    canonical_approval_json = root / (
        "research/archive_inventory/r11a_approval/"
        "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json"
    )
    canonical_approval_text = root / (
        "research/archive_inventory/r11a_approval/"
        "APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt"
    )
    canonical_approval_record_present = (
        canonical_approval_json.exists() or canonical_approval_text.exists()
    )
    require(
        not canonical_approval_record_present,
        "canonical owner approval record already exists",
    )

    runtime_evidence_paths = {
        "runtime_binding": "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
        "runtime_release": "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
        "runtime_activation": "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
        "role_attestation": "research/archive_inventory/r11a_role_attestation/R11A_DEDICATED_ROLE_OPERATOR_ATTESTATION.json",
        "sts_preflight": "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_EVIDENCE.json",
        "workflow_installation": "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION.json",
    }
    runtime_evidence = {
        key: (root / relative).exists()
        for key, relative in runtime_evidence_paths.items()
    }
    for key, relative in runtime_evidence_paths.items():
        require(
            not runtime_evidence[key],
            f"external/runtime authority unexpectedly present: {relative}",
        )

    contract = load(root, CONTRACT)
    require(contract.get("implementation_id") == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7", "R7 contract identity drift")
    require(contract.get("implementation_sealed") is True, "R7 implementation no longer sealed")
    require(contract.get("owner_approval_present") is False, "historical R7 contract claims approval")
    require(contract.get("runtime_authority") and all(value is False for value in contract["runtime_authority"].values()), "R7 contract opens runtime")
    require(contract.get("r11_closed") is False and contract.get("r12_ready") is False, "R7 contract changes scientific gate")

    contract_runtime = contract.get("runtime_authority")
    contract_trading = contract.get("trading_authorizations")
    role_authority = role.get("current_authority")
    envelope_science = envelope.get("prohibited_scientific_scope")
    envelope_authority = envelope.get("authority_state")
    require(isinstance(contract_runtime, dict), "R7 runtime authority absent")
    require(isinstance(contract_trading, dict), "R7 trading authority absent")
    require(isinstance(role_authority, dict), "role current authority absent")
    require(isinstance(envelope_science, dict), "envelope science scope absent")
    require(isinstance(envelope_authority, dict), "envelope authority state absent")

    permission_exact_72 = (
        candidate_identity.get("permission_policy_least_privilege") is True
        and isinstance(resources_allowed, list)
        and len(resources_allowed) == 72
        and set(resources_allowed) == expected_arns
    )
    oidc_restricted = (
        candidate_identity.get("oidc_repository_restricted") is True
        and candidate_identity.get("oidc_branch_ref_restricted") is True
        and candidate_identity.get("oidc_workflow_name_restricted") is True
        and condition == expected_condition
    )
    workflow_exact_hash_bound = (
        candidate_identity.get("workflow_exact_byte_hash_bound_by_package") is True
        and bound_files.get(WORKFLOW) == sha256(root, WORKFLOW)
        and bound_files.get(WORKFLOW) == WORKFLOW_SHA
    )
    workflow_candidate_outside_dot_github = (
        Path(WORKFLOW).parts[:2] != (".github", "workflows")
        and not installed_workflow.exists()
    )
    workflow_lower = workflow_text.lower()
    reusable_credential_tokens = (
        "secrets.",
        "persist-credentials: true",
        "aws-access-key-id:",
        "aws-secret-access-key:",
        "aws-session-token:",
    )
    secrets_or_reusable_credentials = (
        candidate_identity.get("reusable_credentials_or_secrets") is True
        or any(token in workflow_lower for token in reusable_credential_tokens)
    )
    external_infrastructure_created = (
        candidate_identity.get("identity_created") is True
        or role.get("new_role_created_by_this_decision") is True
        or any(value is True for value in role_authority.values())
        or installed_workflow.exists()
        or runtime_evidence["role_attestation"]
        or runtime_evidence["sts_preflight"]
        or runtime_evidence["workflow_installation"]
    )
    iam_ready = (
        permission_exact_72
        and oidc_restricted
        and workflow_exact_hash_bound
        and workflow_candidate_outside_dot_github
        and not secrets_or_reusable_credentials
        and not external_infrastructure_created
    )

    runtime_authority = {
        "successor_role_created": role.get("new_role_created_by_this_decision") is True,
        "aws_iam_mutation": (
            role_authority.get("iam_role_creation") is True
            or role_authority.get("iam_policy_application") is True
            or contract_runtime.get("aws_iam_mutation") is True
            or contract.get("aws_iam_mutations_executed_by_implementation") != 0
        ),
        "aws_oidc": (
            role_authority.get("aws_oidc") is True
            or contract_runtime.get("aws_oidc") is True
            or runtime_evidence["sts_preflight"]
        ),
        "sts": (
            role_authority.get("sts") is True
            or contract_runtime.get("sts") is True
            or runtime_evidence["sts_preflight"]
        ),
        "workflow_installed": (
            package_runtime.get("workflow_installed") is True
            or installed_workflow.exists()
            or runtime_evidence["workflow_installation"]
        ),
        "runtime_binding_present": (
            package_runtime.get("runtime_binding_present") is True
            or runtime_evidence["runtime_binding"]
        ),
        "runtime_release": (
            package_runtime.get("execution_release_present") is True
            or runtime_evidence["runtime_release"]
        ),
        "runtime_activation": (
            package_runtime.get("runtime_activation_present") is True
            or runtime_evidence["runtime_activation"]
        ),
        "requester_pays": contract_runtime.get("requester_pays") is True,
        "get_object": (
            contract_runtime.get("get_object") is True
            or role_authority.get("s3") is True
        ),
        "object_body_download": contract_runtime.get("object_body_download") is True,
        "decompression": contract_runtime.get("decompression") is True,
        "diagnostic_execution": (
            package_runtime.get("diagnostic_execution") is True
            or contract_runtime.get("diagnostic_processing") is True
            or contract.get("network_requests_executed_by_implementation") != 0
            or contract.get("diagnostic_rows_created_by_implementation") != 0
        ),
        "diagnostic_artifact_retention": (
            contract_runtime.get("diagnostic_artifact_retention") is True
        ),
    }

    science_state = {
        "empirical_root_cause": package_science.get("empirical_root_cause"),
        "deduplication": (
            not_authorized.get("deduplication") is True
            or envelope_science.get("deduplication") is True
        ),
        "replay_suppression": (
            not_authorized.get("replay_suppression") is True
            or envelope_science.get("block_replay_suppression") is True
        ),
        "r11b_repair": (
            not_authorized.get("r11b_repair") is True
            or envelope_science.get("r11b_repair") is True
        ),
        "wallet_ranking": (
            not_authorized.get("wallet_ranking") is True
            or envelope_science.get("wallet_ranking") is True
        ),
        "copyability": (
            not_authorized.get("copyability_analysis") is True
            or envelope_science.get("copyability_analysis") is True
        ),
        "r11_closed": (
            package_science.get("r11_closed") is True
            or envelope_authority.get("r11_closed") is True
            or contract.get("r11_closed") is True
        ),
        "r12_ready": (
            package_science.get("r12_ready") is True
            or envelope_authority.get("r12_ready") is True
            or contract.get("r12_ready") is True
        ),
    }
    trading_authorizations = {
        "integration": (
            not_authorized.get("trading_integration") is True
            or contract_trading.get("integration") is True
        ),
        "paper": (
            not_authorized.get("paper_trading") is True
            or contract_trading.get("paper") is True
        ),
        "shadow": (
            not_authorized.get("shadow_trading") is True
            or contract_trading.get("shadow") is True
        ),
        "live": (
            not_authorized.get("live_orders") is True
            or contract_trading.get("live") is True
        ),
        "leverage": (
            not_authorized.get("leverage") is True
            or contract_trading.get("leverage") is True
        ),
        "capital_allocation": (
            not_authorized.get("capital_allocation") is True
            or contract_trading.get("capital_allocation") is True
        ),
    }

    package_approval_record = package.get("canonical_approval_record", {})
    owner_approval_present = (
        package.get("owner_approval_present") is True
        or package_approval_record.get("present_now") is True
        or canonical_approval_record_present
    )
    pricing_ready = (
        pricing.get("status") == "PASS_CURRENT_OFFICIAL_PRICING_BOUND_NO_EXECUTION"
        and pricing.get("pricing_binding_pending") is False
        and calculation.get("total_raw_max_eur_ceil_6dp") == ceil_six(total_eur)
        and calculation.get("projected_with_contingency_eur_ceil_6dp")
        == ceil_six(projected_eur)
        and calculation.get("owner_approval_max_eur") == "0.500000"
        and calculation.get("monthly_recurring_budget_eur") == "0.000000"
    )
    owner_approval_ready = (
        pricing_ready
        and iam_ready
        and package.get("approval_status") == "AWAITING_EXPLICIT_OWNER_APPROVAL"
        and not owner_approval_present
        and not any(runtime_authority.values())
    )

    envelope_anchor = envelope.get("software_anchor", {})
    sha_drift = (
        anchor.get("reviewed_head") != envelope_anchor.get("reviewed_head")
        or anchor.get("reviewed_head") != GREEN_HEAD
        or anchor.get("base_sha") != BASE_SHA
    )

    expected_status = {
        "schema_version": "1.1",
        "status_id": "R11A-G1-POST-GREEN-READINESS-STATUS-001",
        "status": "OWNER_APPROVAL_READY_AWAITING_EXPLICIT_OWNER_APPROVAL_NO_RUNTIME",
        "decision": "OWNER_APPROVAL_READY",
        "repository": "Mathisve1/onchain-wallet-intelligence-lab",
        "software_anchor": {
            "review_id": anchor.get("authoritative_review_id"),
            "review_event": anchor.get("review_event"),
            "review_verdict": anchor.get("review_verdict"),
            "reviewed_head": anchor.get("reviewed_head"),
            "reviewed_tree": GREEN_TREE,
            "base_sha": anchor.get("base_sha"),
            "sha_drift": sha_drift,
            "superseding_red_review_present": anchor.get(
                "superseding_red_review_present"
            ),
            "verified_against_live_github_on_date_utc": "2026-08-25",
        },
        "historical_r7_seal": {
            "semantics": "PRE_REVIEW_IMPLEMENTATION_STAGE_HISTORICAL_SEAL",
            "reviewed_head_contract_sha256": anchor.get(
                "reviewed_head_contract_sha256"
            ),
            "reviewed_head_status_sha256": sha256(root, R7_STATUS),
            "historical_semantics_rewritten": False,
            "successor_manifest_projection_may_be_mechanically_resealed": True,
        },
        "current_bindings": {
            "execution_envelope_path": ENVELOPE,
            "execution_envelope_sha256": sha256(root, ENVELOPE),
            "pricing_eur_binding_path": PRICING,
            "pricing_eur_binding_sha256": sha256(root, PRICING),
            "runtime_pricing_candidate_path": RUNTIME_PRICING_CANDIDATE,
            "runtime_pricing_candidate_sha256": sha256(
                root, RUNTIME_PRICING_CANDIDATE
            ),
            "owner_approval_package_path": PACKAGE,
            "owner_approval_package_sha256": sha256(root, PACKAGE),
            "proposed_owner_statement_path": STATEMENT,
            "proposed_owner_statement_sha256": sha256(root, STATEMENT),
        },
        "pricing": {
            "current_official_binding": "PASS" if pricing_ready else "FAIL",
            "pricing_binding_pending": pricing.get("pricing_binding_pending"),
            "raw_max_eur_ceil_6dp": calculation.get(
                "total_raw_max_eur_ceil_6dp"
            ),
            "projected_with_contingency_eur_ceil_6dp": calculation.get(
                "projected_with_contingency_eur_ceil_6dp"
            ),
            "owner_approval_max_eur": calculation.get("owner_approval_max_eur"),
            "monthly_recurring_budget_eur": calculation.get(
                "monthly_recurring_budget_eur"
            ),
        },
        "iam_workflow_readiness": {
            "status": "PASS_INERT_LEAST_PRIVILEGE" if iam_ready else "FAIL",
            "permission_policy_exact_72_getobject_resources": permission_exact_72,
            "oidc_repository_owner_ref_and_workflow_restricted": oidc_restricted,
            "workflow_exact_hash_bound": workflow_exact_hash_bound,
            "workflow_candidate_outside_dot_github": workflow_candidate_outside_dot_github,
            "secrets_or_reusable_credentials": secrets_or_reusable_credentials,
            "external_infrastructure_created": external_infrastructure_created,
        },
        "owner_approval": {
            "approval_id": package.get("proposed_approval_id"),
            "approval_status": package.get("approval_status"),
            "owner_approval_ready": owner_approval_ready,
            "owner_approval_present": owner_approval_present,
            "canonical_approval_record_present": canonical_approval_record_present,
        },
        "runtime_authority": runtime_authority,
        "science_state": science_state,
        "trading_authorizations": trading_authorizations,
    }
    classified_paths = set(STATUS_FIELD_CLASSIFICATION)
    require(
        len(classified_paths) == 75,
        "status classification registry does not contain exact 75 leaves",
    )
    require(
        set(STATUS_FIELD_CLASSIFICATION.values()) == {"A", "B", "C"},
        "status classification registry has invalid or missing categories",
    )
    require(
        not STATUS_INFORMATIONAL_FIELDS,
        "authoritative G1 status unexpectedly contains D fields",
    )
    require(
        classified_paths == scalar_leaf_paths(expected_status),
        "status classification registry does not match exact status schema",
    )
    status = load(root, STATUS)
    require_exact(status, expected_status, "G1 status projection")


def main() -> int:
    validate(ROOT)
    print("R11A_G1_OWNER_APPROVAL_READINESS_VALID_AWAITING_EXPLICIT_APPROVAL_NO_RUNTIME")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
