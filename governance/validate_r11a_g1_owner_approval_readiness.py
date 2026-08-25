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

    status = load(root, STATUS)
    require(status.get("decision") == "OWNER_APPROVAL_READY", "G1 readiness decision drift")
    require(status.get("status") == "OWNER_APPROVAL_READY_AWAITING_EXPLICIT_OWNER_APPROVAL_NO_RUNTIME", "G1 status drift")
    status_anchor = status.get("software_anchor", {})
    require(status_anchor.get("reviewed_head") == GREEN_HEAD and status_anchor.get("reviewed_tree") == GREEN_TREE, "status software anchor drift")
    require(status_anchor.get("base_sha") == BASE_SHA and status_anchor.get("sha_drift") is False, "status base/drift truth mismatch")
    current = status.get("current_bindings", {})
    require(current.get("execution_envelope_sha256") == ENVELOPE_SHA, "status envelope binding drift")
    require(current.get("pricing_eur_binding_sha256") == PRICING_SHA, "status pricing binding drift")
    require(current.get("runtime_pricing_candidate_sha256") == RUNTIME_PRICING_CANDIDATE_SHA, "status runtime pricing binding drift")
    require(current.get("owner_approval_package_sha256") == PACKAGE_SHA, "status package binding drift")
    require(current.get("proposed_owner_statement_sha256") == STATEMENT_SHA, "status statement binding drift")
    owner = status.get("owner_approval", {})
    require(owner.get("owner_approval_ready") is True, "owner approval is not ready")
    require(owner.get("owner_approval_present") is False, "owner approval falsely present")
    require(owner.get("approval_status") == "AWAITING_EXPLICIT_OWNER_APPROVAL", "owner approval status drift")
    require_all_false(status.get("runtime_authority"), "status runtime authority")
    science = status.get("science_state", {})
    require(science.get("empirical_root_cause") == "UNKNOWN_PENDING_DIAGNOSTIC", "empirical root cause falsely claimed")
    require(all(value is False for key, value in science.items() if key != "empirical_root_cause"), "science authority opened")
    require_all_false(status.get("trading_authorizations"), "status trading authority")

    canonical_approval_json = root / "research/archive_inventory/r11a_approval/APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.json"
    canonical_approval_text = root / "research/archive_inventory/r11a_approval/APPROVE_HL_ARCHIVE_R11A_IDENTITY_BOUNDARY_DIAGNOSTIC_001.txt"
    require(not canonical_approval_json.exists() and not canonical_approval_text.exists(), "canonical owner approval record already exists")
    for relative in (
        "research/archive_inventory/r11a_runtime/R11A_RUNTIME_BINDING_R7.json",
        "research/archive_inventory/r11a_runtime/R11A_EXECUTION_RELEASE.json",
        "research/archive_inventory/r11a_runtime/R11A_CANONICAL_ACTIVATION.json",
        "research/archive_inventory/r11a_role_attestation/R11A_DEDICATED_ROLE_OPERATOR_ATTESTATION.json",
        "research/archive_inventory/r11a_role_preflight/R11A_STS_PREFLIGHT_EVIDENCE.json",
        "research/archive_inventory/r11a_workflow_installation/R11A_WORKFLOW_INSTALLATION.json",
    ):
        require(not (root / relative).exists(), f"external/runtime authority unexpectedly present: {relative}")

    contract = load(root, CONTRACT)
    require(contract.get("implementation_id") == "HL-ARCHIVE-R11A-IDENTITY-BOUNDARY-DIAGNOSTIC-CORRECTIVE-R7", "R7 contract identity drift")
    require(contract.get("implementation_sealed") is True, "R7 implementation no longer sealed")
    require(contract.get("owner_approval_present") is False, "historical R7 contract claims approval")
    require(contract.get("runtime_authority") and all(value is False for value in contract["runtime_authority"].values()), "R7 contract opens runtime")
    require(contract.get("r11_closed") is False and contract.get("r12_ready") is False, "R7 contract changes scientific gate")


def main() -> int:
    validate(ROOT)
    print("R11A_G1_OWNER_APPROVAL_READINESS_VALID_AWAITING_EXPLICIT_APPROVAL_NO_RUNTIME")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
