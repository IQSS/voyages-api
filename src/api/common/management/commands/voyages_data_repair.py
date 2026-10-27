from __future__ import annotations

import base64
import datetime as dt
import decimal
import hashlib
import json
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable, Sequence

import boto3
import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


SCHEMA_VERSION = 1
BATCH_SIZE = 500
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
REPAIR_ID = re.compile(r"^[a-z0-9][a-z0-9-]*-v[0-9]+$")
CANDIDATE_DATABASE = re.compile(r"^voyages_api_candidate_[ab]$")
PRODUCTION_DATABASE = "voyages_api"
PINNED_RDS_CA_PATH = "/etc/ssl/certs/aws-rds-us-east-1-bundle.pem"
PINNED_RDS_CA_SHA256 = (
    "b1711d12bae51838581281e23b6cb97b1074016873b4dafc80ed14002462dd77"
)
PINNED_RDS_CLIENT_CONFIG = "/etc/mysql/voyages-rds-client.cnf"
PINNED_RDS_CLIENT_CONFIG_SHA256 = (
    "2c3da2c1efc53d6be58c32c78f744263005a5e73ad16ca0616de287dfa18355f"
)
FORBIDDEN_TABLES = {
    "auth_user",
    "auth_user_groups",
    "auth_user_user_permissions",
    "authtoken_token",
    "captcha_captchastore",
    "common_savedquery",
    "django_admin_log",
    "django_session",
}
EXPECTED_IMAGE = object()


class RepairError(Exception):
    """A redacted, operator-actionable repair failure."""


@dataclass(frozen=True)
class RepairBundle:
    repair_id: str
    directory: Path
    descriptor: dict[str, Any]
    operations: tuple[dict[str, Any], ...]
    manifest_sha256: str


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RepairError(f"{label} must be an object")
    return value


def quote_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise RepairError("repair contains an invalid SQL identifier")
    return f"`{value}`"


def normalize_value(value: Any, expected: Any = None) -> Any:
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.loads(canonical_json(value))
    if isinstance(expected, (dict, list)) and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def database_parameter(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return canonical_json(value)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RepairError(f"unable to read {path.name}") from exc
    return require_mapping(value, path.name)


def validate_operation(
    operation: dict[str, Any],
    expected_sequence: int,
    expected_repair_id: str,
    allowed_tables: set[str],
) -> None:
    required = {
        "repair_id",
        "sequence",
        "action",
        "table",
        "key",
        "before",
        "after",
    }
    if set(operation) != required:
        raise RepairError("manifest operation fields do not match the schema")
    if operation["sequence"] != expected_sequence:
        raise RepairError("manifest sequence is not contiguous")
    if operation["repair_id"] != expected_repair_id:
        raise RepairError("manifest operation belongs to a different repair")
    if operation["action"] not in {"insert", "update", "delete"}:
        raise RepairError("manifest action is not supported")
    table = operation["table"]
    if table not in allowed_tables or table in FORBIDDEN_TABLES:
        raise RepairError("manifest references a forbidden table")
    quote_identifier(table)
    key = require_mapping(operation["key"], "operation key")
    if not key:
        raise RepairError("manifest operation has an empty key")
    for column, value in key.items():
        quote_identifier(column)
        if value is None:
            raise RepairError("manifest operation key contains null")
    before = operation["before"]
    after = operation["after"]
    if before is not None:
        before = require_mapping(before, "operation before")
        for column, value in before.items():
            quote_identifier(column)
            if column in key and key[column] != value:
                raise RepairError("operation key and before image disagree")
    if after is not None:
        after = require_mapping(after, "operation after")
        for column, value in after.items():
            quote_identifier(column)
            if column in key and key[column] != value:
                raise RepairError("operation key and after image disagree")
    action = operation["action"]
    if action == "insert" and (before is not None or not after):
        raise RepairError("insert must have null before and a nonempty after")
    if action == "update" and (not before or not after):
        raise RepairError("update must have nonempty before and after")
    if action == "update" and set(before) != set(after):
        raise RepairError("update before and after column sets differ")
    if action == "delete" and (not before or after is not None):
        raise RepairError("delete must have nonempty before and null after")


def load_bundle(root: Path, repair_id: str) -> RepairBundle:
    if not REPAIR_ID.fullmatch(repair_id):
        raise RepairError("repair set contains an invalid repair id")
    directory = root / repair_id
    descriptor_path = directory / "repair.yaml"
    manifest_path = directory / "manifest.jsonl"
    descriptor = load_yaml(descriptor_path)
    if descriptor.get("id") != repair_id:
        raise RepairError("repair descriptor id does not match its directory")
    allowed_tables = set(descriptor.get("allowed_tables") or [])
    forbidden_tables = set(descriptor.get("forbidden_tables") or [])
    if not allowed_tables:
        raise RepairError("repair descriptor has no allowed tables")
    if not FORBIDDEN_TABLES.issubset(forbidden_tables):
        raise RepairError("repair descriptor omits mandatory forbidden tables")
    if allowed_tables & forbidden_tables:
        raise RepairError("repair descriptor allows a forbidden table")
    for table in allowed_tables | forbidden_tables:
        quote_identifier(table)

    actual_manifest_sha = sha256_file(manifest_path)
    if descriptor.get("manifest_sha256") != actual_manifest_sha:
        raise RepairError("repair manifest checksum does not match descriptor")
    operations: list[dict[str, Any]] = []
    operation_counts: Counter[tuple[str, str]] = Counter()
    seen_keys: set[tuple[str, str]] = set()
    for line_number, raw_line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line or raw_line != raw_line.strip():
            raise RepairError("manifest is not canonical JSONL")
        try:
            operation = require_mapping(json.loads(raw_line), "manifest operation")
        except json.JSONDecodeError as exc:
            raise RepairError("manifest contains invalid JSON") from exc
        if raw_line != canonical_json(operation):
            raise RepairError("manifest JSON is not canonical")
        validate_operation(operation, line_number, repair_id, allowed_tables)
        key_marker = (operation["table"], canonical_json(operation["key"]))
        if key_marker in seen_keys:
            raise RepairError("repair manifest repeats a table/key")
        seen_keys.add(key_marker)
        operation_counts[(operation["table"], operation["action"])] += 1
        operations.append(operation)
    if not operations:
        raise RepairError("repair manifest is empty")
    expected = require_mapping(descriptor.get("expected"), "repair expected")
    if expected.get("operation_count") != len(operations):
        raise RepairError("repair operation count does not match descriptor")
    expected_actions = require_mapping(
        expected.get("actions"), "repair expected action counts"
    )
    for action in ("insert", "update", "delete"):
        actual_count = sum(
            count
            for (_, candidate_action), count in operation_counts.items()
            if candidate_action == action
        )
        if expected_actions.get(action) != actual_count:
            raise RepairError("repair action count does not match descriptor")
    expected_tables = require_mapping(
        expected.get("tables"), "repair expected table counts"
    )
    if set(expected_tables) != allowed_tables:
        raise RepairError("repair expected-table list does not match allowlist")
    for table in allowed_tables:
        table_counts = require_mapping(
            expected_tables.get(table), "repair expected table action counts"
        )
        for action in ("insert", "update", "delete"):
            if table_counts.get(action) != operation_counts[(table, action)]:
                raise RepairError("repair table/action count does not match descriptor")
    verification = require_mapping(
        descriptor.get("verification"), "repair verification"
    )
    sentinels = verification.get("sentinels")
    minimum = min(3, len(operations))
    if not isinstance(sentinels, list) or len(sentinels) < minimum:
        raise RepairError("repair has too few verification sentinels")
    operation_by_key = {
        (operation["table"], canonical_json(operation["key"])): operation
        for operation in operations
    }
    for sentinel in sentinels:
        sentinel = require_mapping(sentinel, "repair sentinel")
        marker = (
            sentinel.get("table"),
            canonical_json(sentinel.get("key")),
        )
        operation = operation_by_key.get(marker)
        if operation is None:
            raise RepairError("repair sentinel does not reference an operation")
        for image_name in ("before", "after"):
            if not partial_matches(
                sentinel.get(image_name), operation.get(image_name)
            ):
                raise RepairError("repair sentinel image disagrees with manifest")
    return RepairBundle(
        repair_id=repair_id,
        directory=directory,
        descriptor=descriptor,
        operations=tuple(operations),
        manifest_sha256=actual_manifest_sha,
    )


def load_repair_set(root: Path, repair_set: str) -> tuple[dict[str, Any], tuple[RepairBundle, ...], str]:
    if not REPAIR_ID.fullmatch(repair_set):
        raise RepairError("invalid repair-set id")
    set_path = root / "sets" / f"{repair_set}.yaml"
    descriptor = load_yaml(set_path)
    if descriptor.get("id") != repair_set:
        raise RepairError("repair-set id does not match its filename")
    repair_ids = descriptor.get("repairs")
    if not isinstance(repair_ids, list) or not repair_ids:
        raise RepairError("repair set has no ordered repairs")
    if len(repair_ids) != len(set(repair_ids)):
        raise RepairError("repair set contains duplicate repairs")
    bundles = tuple(load_bundle(root, repair_id) for repair_id in repair_ids)
    digest_input = {
        "repair_set": repair_set,
        "repair_set_descriptor_sha256": sha256_file(set_path),
        "repairs": [
            {
                "descriptor_sha256": sha256_file(
                    bundle.directory / "repair.yaml"
                ),
                "id": bundle.repair_id,
                "manifest_sha256": bundle.manifest_sha256,
            }
            for bundle in bundles
        ],
        "schema_version": 1,
    }
    return descriptor, bundles, sha256_bytes(canonical_json(digest_input).encode())


def partial_matches(expected: Any, actual: Any) -> bool:
    if expected is None:
        return actual is None
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return normalize_value(expected) == normalize_value(actual, expected)
    return all(
        name in actual and partial_matches(value, actual[name])
        for name, value in expected.items()
    )


def selected_columns(operation: dict[str, Any]) -> list[str]:
    columns = set(operation["key"])
    for image in (operation["before"], operation["after"]):
        if isinstance(image, dict):
            columns.update(image)
    return sorted(columns)


def where_clause(values: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    for column in sorted(values):
        value = values[column]
        if value is None:
            clauses.append(f"{quote_identifier(column)} IS NULL")
        else:
            clauses.append(f"{quote_identifier(column)} = %s")
            parameters.append(database_parameter(value))
    return " AND ".join(clauses), parameters


def operation_token(operation: dict[str, Any]) -> tuple[str, int]:
    return operation["repair_id"], operation["sequence"]


def batched(values: Sequence[Any], size: int = BATCH_SIZE) -> Iterable[Sequence[Any]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def normalized_key(values: dict[str, Any], columns: Sequence[str]) -> str:
    return canonical_json(
        {column: normalize_value(values[column]) for column in columns}
    )


def fetch_operation_rows(
    cursor: Any, bundles: Iterable[RepairBundle]
) -> dict[tuple[str, int], dict[str, Any] | None]:
    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for bundle in bundles:
        for operation in bundle.operations:
            groups[
                (operation["table"], tuple(sorted(operation["key"])))
            ].append(operation)

    result: dict[tuple[str, int], dict[str, Any] | None] = {}
    for (table, key_columns), operations in groups.items():
        columns = sorted(
            {
                column
                for operation in operations
                for column in selected_columns(operation)
            }
        )
        for operation_batch in batched(operations):
            key_width = len(key_columns)
            if key_width == 1:
                key_expression = quote_identifier(key_columns[0])
                placeholders = ",".join(["%s"] * len(operation_batch))
            else:
                row_placeholder = "(" + ",".join(["%s"] * key_width) + ")"
                placeholders = ",".join(
                    [row_placeholder] * len(operation_batch)
                )
                key_expression = "(" + ",".join(
                    quote_identifier(column) for column in key_columns
                ) + ")"
            parameters = [
                database_parameter(operation["key"][column])
                for operation in operation_batch
                for column in key_columns
            ]
            cursor.execute(
                "SELECT "
                + ",".join(quote_identifier(column) for column in columns)
                + f" FROM {quote_identifier(table)} WHERE "
                + f"{key_expression} IN ({placeholders})",
                parameters,
            )
            rows_by_key: dict[str, dict[str, Any]] = {}
            for raw_row in cursor.fetchall():
                row = dict(zip(columns, raw_row))
                key_value = normalized_key(row, key_columns)
                if key_value in rows_by_key:
                    raise RepairError("repair key matched more than one row")
                rows_by_key[key_value] = row
            for operation in operation_batch:
                key_value = normalized_key(operation["key"], key_columns)
                token = operation_token(operation)
                if token in result:
                    raise RepairError("repair manifest contains a duplicate operation")
                result[token] = rows_by_key.get(key_value)
    return result


def image_matches(row: dict[str, Any] | None, image: dict[str, Any] | None) -> bool:
    if image is None:
        return row is None
    if row is None:
        return False
    return all(
        normalize_value(row.get(column), expected) == normalize_value(expected)
        for column, expected in image.items()
    )


def projection_entry(
    operation: dict[str, Any],
    image_name: str,
    row: dict[str, Any] | None | object = EXPECTED_IMAGE,
) -> dict[str, Any]:
    expected = operation[image_name]
    if row is EXPECTED_IMAGE:
        image = expected
    elif expected is None:
        image = None
    elif row is None:
        image = None
    else:
        image = {
            column: normalize_value(row.get(column), value)
            for column, value in sorted(expected.items())
        }
    return {
        "repair_id": operation["repair_id"],
        "sequence": operation["sequence"],
        "table": operation["table"],
        "key": operation["key"],
        "image": image,
    }


def expected_projection_digest(bundle: RepairBundle, image_name: str) -> str:
    entries = [projection_entry(operation, image_name) for operation in bundle.operations]
    return sha256_bytes(canonical_json(entries).encode())


def live_projection_digest(
    bundle: RepairBundle,
    image_name: str,
    rows: dict[tuple[str, int], dict[str, Any] | None],
) -> str:
    entries = []
    for operation in bundle.operations:
        row = rows[operation_token(operation)]
        entries.append(projection_entry(operation, image_name, row))
    return sha256_bytes(canonical_json(entries).encode())


def validate_projection_digests(bundle: RepairBundle) -> None:
    verification = require_mapping(
        bundle.descriptor.get("verification"), "repair verification"
    )
    for image_name in ("before", "after"):
        field = "preimage_sha256" if image_name == "before" else "postimage_sha256"
        if verification.get(field) != expected_projection_digest(bundle, image_name):
            raise RepairError(f"repair {field} does not match its manifest")


def operation_state(
    operation: dict[str, Any], row: dict[str, Any] | None
) -> str:
    before = operation["before"]
    after = operation["after"]
    if operation["action"] == "insert":
        if row is None:
            return "pending"
        if image_matches(row, after):
            return "applied"
    elif operation["action"] == "delete":
        if row is None:
            return "applied"
        if image_matches(row, before):
            return "pending"
    else:
        if image_matches(row, after):
            return "applied"
        if image_matches(row, before):
            return "pending"
    return "conflict"


def inspect_operations(
    cursor: Any, bundles: Sequence[RepairBundle]
) -> tuple[list[str], dict[tuple[str, int], dict[str, Any] | None]]:
    rows = fetch_operation_rows(cursor, bundles)
    states = [
        operation_state(operation, rows[operation_token(operation)])
        for bundle in bundles
        for operation in bundle.operations
    ]
    return states, rows


def live_digest_evidence(
    bundles: Iterable[RepairBundle],
    image_name: str,
    rows: dict[tuple[str, int], dict[str, Any] | None],
) -> dict[str, str]:
    return {
        bundle.repair_id: live_projection_digest(bundle, image_name, rows)
        for bundle in bundles
    }


def expected_digest_evidence(
    bundles: Iterable[RepairBundle], image_name: str
) -> dict[str, str]:
    field = "preimage_sha256" if image_name == "before" else "postimage_sha256"
    return {
        bundle.repair_id: bundle.descriptor["verification"][field]
        for bundle in bundles
    }


def sentinel_evidence(
    bundles: Iterable[RepairBundle],
    image_name: str,
    rows: dict[tuple[str, int], dict[str, Any] | None],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for bundle in bundles:
        operations = {
            (operation["table"], canonical_json(operation["key"])): operation
            for operation in bundle.operations
        }
        verification = require_mapping(
            bundle.descriptor.get("verification"), "repair verification"
        )
        for sentinel in verification["sentinels"]:
            operation = operations[
                (sentinel["table"], canonical_json(sentinel["key"]))
            ]
            row = rows[operation_token(operation)]
            expected = sentinel[image_name]
            passed = image_matches(row, expected)
            evidence.append(
                {
                    "repairId": bundle.repair_id,
                    "id": sentinel["id"],
                    "image": image_name,
                    "passed": passed,
                }
            )
            if not passed:
                raise RepairError("repair sentinel does not match live data")
    return evidence


def manifest_duration_expectations(
    bundle: RepairBundle, duration_field: str
) -> dict[int, int]:
    expectations: dict[int, int] = {}
    for operation in bundle.operations:
        if (
            operation["action"] != "update"
            or operation["table"] != "voyage_voyagedates"
            or set(operation["key"]) != {"voyage_id"}
            or set(operation["after"]) != {duration_field}
        ):
            raise RepairError("duration assertion has an incompatible manifest")
        voyage_id = operation["key"]["voyage_id"]
        duration = operation["after"][duration_field]
        if not isinstance(voyage_id, int) or not isinstance(duration, int):
            raise RepairError("duration assertion requires integer values")
        expectations[voyage_id] = duration
    if len(expectations) != len(bundle.operations):
        raise RepairError("duration assertion manifest repeats a voyage")
    return expectations


def actual_duration_rows(
    cursor: Any,
    voyage_ids: Sequence[int],
    departure_field: str,
    arrival_field: str,
    duration_field: str,
) -> dict[int, dict[str, Any]]:
    approved_fields = (
        "date_departed_africa_sparsedate_id",
        "first_dis_of_slaves_sparsedate_id",
        "length_middle_passage_days",
    )
    if (departure_field, arrival_field, duration_field) != approved_fields:
        raise RepairError("duration assertion uses unapproved date fields")
    rows: dict[int, dict[str, Any]] = {}
    for voyage_batch in batched(voyage_ids):
        placeholders = ",".join(["%s"] * len(voyage_batch))
        cursor.execute(
            "SELECT vd.voyage_id, dep.year, dep.month, dep.day, "
            "arr.year, arr.month, arr.day, "
            f"vd.{quote_identifier(duration_field)}, "
            "DATEDIFF("
            "STR_TO_DATE(CONCAT(arr.year, '-', LPAD(arr.month, 2, '0'), "
            "'-', LPAD(arr.day, 2, '0')), '%%Y-%%m-%%d'), "
            "STR_TO_DATE(CONCAT(dep.year, '-', LPAD(dep.month, 2, '0'), "
            "'-', LPAD(dep.day, 2, '0')), '%%Y-%%m-%%d')) "
            "FROM voyage_voyagedates vd "
            "JOIN voyage_voyagesparsedate dep ON dep.id = "
            f"vd.{quote_identifier(departure_field)} "
            "JOIN voyage_voyagesparsedate arr ON arr.id = "
            f"vd.{quote_identifier(arrival_field)} "
            f"WHERE vd.voyage_id IN ({placeholders})",
            list(voyage_batch),
        )
        for raw_row in cursor.fetchall():
            (
                voyage_id,
                departure_year,
                departure_month,
                departure_day,
                arrival_year,
                arrival_month,
                arrival_day,
                live_duration,
                calculated_duration,
            ) = raw_row
            if voyage_id in rows:
                raise RepairError("duration assertion matched a voyage twice")
            if None in (
                departure_year,
                departure_month,
                departure_day,
                arrival_year,
                arrival_month,
                arrival_day,
                calculated_duration,
            ):
                raise RepairError("duration assertion found an incomplete actual date")
            try:
                departure = dt.date(
                    int(departure_year), int(departure_month), int(departure_day)
                )
                arrival = dt.date(
                    int(arrival_year), int(arrival_month), int(arrival_day)
                )
            except (TypeError, ValueError) as exc:
                raise RepairError("duration assertion found an invalid actual date") from exc
            rows[int(voyage_id)] = {
                "departure": departure.isoformat(),
                "firstDisembarkation": arrival.isoformat(),
                "liveDuration": live_duration,
                "calculatedDuration": int(calculated_duration),
            }
    return rows


def verify_duration_assertions(
    cursor: Any,
    bundle: RepairBundle,
    assertions: Sequence[dict[str, Any]],
    require_postimage: bool,
) -> list[dict[str, Any]]:
    full_assertions = [
        assertion
        for assertion in assertions
        if assertion.get("kind") == "all_actual_date_differences"
    ]
    if len(full_assertions) != 1:
        raise RepairError("duration repair requires one full-set date assertion")
    assertion = full_assertions[0]
    departure_field = assertion.get("departure_field")
    arrival_field = assertion.get("first_disembarkation_field")
    duration_field = assertion.get("duration_field")
    if not all(
        isinstance(value, str)
        for value in (departure_field, arrival_field, duration_field)
    ):
        raise RepairError("duration assertion fields are invalid")
    expectations = manifest_duration_expectations(bundle, duration_field)
    if assertion.get("expected_count") != len(expectations):
        raise RepairError("duration assertion count disagrees with manifest")
    rows = actual_duration_rows(
        cursor,
        sorted(expectations),
        departure_field,
        arrival_field,
        duration_field,
    )
    if set(rows) != set(expectations):
        raise RepairError("duration assertion did not resolve every voyage")
    for voyage_id, expected_days in expectations.items():
        row = rows[voyage_id]
        if row["calculatedDuration"] != expected_days:
            raise RepairError("duration manifest disagrees with actual dates")
        if require_postimage and row["liveDuration"] != expected_days:
            raise RepairError("duration postimage disagrees with actual dates")

    evidence: list[dict[str, Any]] = [
        {
            "kind": "all_actual_date_differences",
            "count": len(rows),
            "passed": True,
        }
    ]
    for sentinel in assertions:
        if sentinel.get("kind") != "actual_date_difference":
            continue
        voyage_id = sentinel.get("voyage_id")
        row = rows.get(voyage_id)
        if (
            row is None
            or row["departure"] != sentinel.get("departure")
            or row["firstDisembarkation"]
            != sentinel.get("first_disembarkation")
            or row["calculatedDuration"] != sentinel.get("expected_days")
        ):
            raise RepairError("duration date sentinel failed")
        evidence.append(
            {
                "kind": "actual_date_difference",
                "voyageId": voyage_id,
                "passed": True,
            }
        )
    return evidence


def verify_voyage_enslaver_role(cursor: Any, assertion: dict[str, Any]) -> None:
    voyage_id = assertion.get("voyage_id")
    principal_alias = assertion.get("principal_alias")
    role_id = assertion.get("role_id")
    present = assertion.get("present")
    if (
        not isinstance(voyage_id, int)
        or not isinstance(principal_alias, str)
        or not isinstance(role_id, int)
        or not isinstance(present, bool)
    ):
        raise RepairError("voyage enslaver assertion is invalid")
    cursor.execute(
        "SELECT COUNT(*) FROM past_enslavementrelation relation_row "
        "JOIN past_enslaverinrelation in_relation "
        "ON in_relation.relation_id = relation_row.id "
        "JOIN past_enslaveralias alias_row "
        "ON alias_row.id = in_relation.enslaver_alias_id "
        "JOIN past_enslaveridentity identity_row "
        "ON identity_row.id = alias_row.identity_id "
        "JOIN past_enslaverinrelation_roles role_row "
        "ON role_row.enslaverinrelation_id = in_relation.id "
        "WHERE relation_row.voyage_id = %s "
        "AND identity_row.principal_alias = %s "
        "AND role_row.enslaverrole_id = %s",
        [voyage_id, principal_alias, role_id],
    )
    found = int(cursor.fetchone()[0]) > 0
    if found != present:
        raise RepairError("voyage enslaver relationship assertion failed")


def verify_source_pairing(bundle: RepairBundle, expected_count: Any) -> None:
    if not isinstance(expected_count, int):
        raise RepairError("source pairing assertion count is invalid")
    source_ids = {
        operation["key"].get("id")
        for operation in bundle.operations
        if operation["table"] == "document_source"
        and operation["action"] == "insert"
    }
    connection_source_ids = [
        operation["after"].get("source_id")
        for operation in bundle.operations
        if operation["table"] == "document_sourcevoyageconnection"
        and operation["action"] == "insert"
    ]
    if (
        len(source_ids) != expected_count
        or len(connection_source_ids) != expected_count
        or set(connection_source_ids) != source_ids
        or len(set(connection_source_ids)) != len(connection_source_ids)
    ):
        raise RepairError("source-to-voyage pairing assertion failed")


ENSLAVER_CACHE_PROJECTIONS = {
    "roles": {
        "cache_table": "past_enslaveridentity_roles",
        "right_column": "enslaverrole_id",
        "cache_sql": (
            "SELECT cache_row.enslaveridentity_id, cache_row.enslaverrole_id "
            "FROM past_enslaveridentity_roles cache_row "
            "ORDER BY cache_row.enslaveridentity_id, cache_row.enslaverrole_id"
        ),
        "graph_sql": (
            "SELECT DISTINCT identity_row.id, role_row.enslaverrole_id "
            "FROM past_enslaveridentity identity_row "
            "JOIN past_enslaveralias alias_row "
            "ON alias_row.identity_id = identity_row.id "
            "JOIN past_enslaverinrelation in_relation "
            "ON in_relation.enslaver_alias_id = alias_row.id "
            "JOIN past_enslaverinrelation_roles role_row "
            "ON role_row.enslaverinrelation_id = in_relation.id "
            "ORDER BY identity_row.id, role_row.enslaverrole_id"
        ),
    },
    "voyages": {
        "cache_table": "past_enslaveridentity_voyages",
        "right_column": "voyage_id",
        "cache_sql": (
            "SELECT cache_row.enslaveridentity_id, cache_row.voyage_id "
            "FROM past_enslaveridentity_voyages cache_row "
            "ORDER BY cache_row.enslaveridentity_id, cache_row.voyage_id"
        ),
        "graph_sql": (
            "SELECT DISTINCT identity_row.id, relation_row.voyage_id "
            "FROM past_enslaveridentity identity_row "
            "JOIN past_enslaveralias alias_row "
            "ON alias_row.identity_id = identity_row.id "
            "JOIN past_enslaverinrelation in_relation "
            "ON in_relation.enslaver_alias_id = alias_row.id "
            "JOIN past_enslavementrelation relation_row "
            "ON relation_row.id = in_relation.relation_id "
            "WHERE relation_row.voyage_id IS NOT NULL "
            "ORDER BY identity_row.id, relation_row.voyage_id"
        ),
    },
}
ENSLAVER_IDENTITY_TIMESTAMP_PROJECTION = {
    "table": "past_enslaveridentity",
    "id_column": "id",
    "timestamp_column": "last_updated",
    "sql": (
        "SELECT identity_row.id, identity_row.last_updated "
        "FROM past_enslaveridentity identity_row "
        "ORDER BY identity_row.id"
    ),
}


def validated_enslaver_cache_projections(
    assertion: dict[str, Any],
) -> list[dict[str, Any]]:
    if set(assertion) != {"kind", "projections", "identity_timestamps"}:
        raise RepairError("enslaver cache assertion fields are invalid")
    values = assertion.get("projections")
    if not isinstance(values, list) or len(values) != len(
        ENSLAVER_CACHE_PROJECTIONS
    ):
        raise RepairError("enslaver cache assertion projections are invalid")
    configured: dict[str, dict[str, Any]] = {}
    required_fields = {
        "name",
        "cache_table",
        "right_column",
        "expected_count",
        "expected_sha256",
    }
    for value in values:
        projection = require_mapping(value, "enslaver cache projection")
        if set(projection) != required_fields:
            raise RepairError("enslaver cache projection fields are invalid")
        name = projection.get("name")
        definition = ENSLAVER_CACHE_PROJECTIONS.get(name)
        if definition is None or name in configured:
            raise RepairError("enslaver cache projection name is invalid")
        if (
            projection.get("cache_table") != definition["cache_table"]
            or projection.get("right_column") != definition["right_column"]
        ):
            raise RepairError("enslaver cache projection target is invalid")
        expected_count = projection.get("expected_count")
        expected_sha256 = projection.get("expected_sha256")
        if type(expected_count) is not int or expected_count < 0:
            raise RepairError("enslaver cache projection count is invalid")
        if not isinstance(expected_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_sha256
        ):
            raise RepairError("enslaver cache projection digest is invalid")
        configured[name] = projection
    if set(configured) != set(ENSLAVER_CACHE_PROJECTIONS):
        raise RepairError("enslaver cache assertion projections are incomplete")
    return [configured[name] for name in ("roles", "voyages")]


def validated_enslaver_identity_timestamps(
    assertion: dict[str, Any],
) -> dict[str, Any]:
    projection = require_mapping(
        assertion.get("identity_timestamps"),
        "enslaver identity timestamp projection",
    )
    required_fields = {
        "table",
        "id_column",
        "timestamp_column",
        "expected_count",
        "expected_sha256",
    }
    if set(projection) != required_fields:
        raise RepairError("enslaver identity timestamp fields are invalid")
    definition = ENSLAVER_IDENTITY_TIMESTAMP_PROJECTION
    if any(
        projection.get(field) != definition[field]
        for field in ("table", "id_column", "timestamp_column")
    ):
        raise RepairError("enslaver identity timestamp target is invalid")
    expected_count = projection.get("expected_count")
    expected_sha256 = projection.get("expected_sha256")
    if type(expected_count) is not int or expected_count < 0:
        raise RepairError("enslaver identity timestamp count is invalid")
    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise RepairError("enslaver identity timestamp digest is invalid")
    return projection


def fetch_enslaver_cache_pairs(
    cursor: Any, sql: str, label: str
) -> set[tuple[int, int]]:
    cursor.execute(sql)
    raw_rows = cursor.fetchall()
    pairs: set[tuple[int, int]] = set()
    for raw_row in raw_rows:
        if not isinstance(raw_row, (tuple, list)) or len(raw_row) != 2:
            raise RepairError(f"{label} returned an invalid row")
        left, right = raw_row
        if (
            type(left) is not int
            or type(right) is not int
            or left < 1
            or right < 1
        ):
            raise RepairError(f"{label} returned an invalid key")
        pairs.add((left, right))
    if len(pairs) != len(raw_rows):
        raise RepairError(f"{label} returned duplicate logical keys")
    return pairs


def enslaver_cache_projection_digest(
    pairs: Iterable[tuple[int, int]], right_column: str
) -> tuple[int, str]:
    entries = [
        {"enslaveridentity_id": left, right_column: right}
        for left, right in sorted(pairs)
    ]
    return len(entries), sha256_bytes(canonical_json(entries).encode())


def normalize_enslaver_identity_timestamp(value: Any) -> str:
    if isinstance(value, dt.datetime):
        timestamp = value
    elif isinstance(value, str):
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})?",
            value,
        ):
            raise RepairError("enslaver identity timestamp is invalid")
        try:
            iso_value = value.replace(" ", "T", 1)
            if iso_value.endswith("Z"):
                iso_value = iso_value[:-1] + "+00:00"
            timestamp = dt.datetime.fromisoformat(iso_value)
        except ValueError as exc:
            raise RepairError("enslaver identity timestamp is invalid") from exc
    else:
        raise RepairError("enslaver identity timestamp is invalid")
    if timestamp.tzinfo is not None and timestamp.utcoffset() is not None:
        timestamp = timestamp.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return timestamp.isoformat(timespec="microseconds")


def enslaver_identity_timestamp_digest(cursor: Any) -> tuple[int, str]:
    cursor.execute(ENSLAVER_IDENTITY_TIMESTAMP_PROJECTION["sql"])
    raw_rows = cursor.fetchall()
    entries: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for raw_row in raw_rows:
        if not isinstance(raw_row, (tuple, list)) or len(raw_row) != 2:
            raise RepairError("enslaver identity timestamp projection returned an invalid row")
        identity_id, last_updated = raw_row
        if type(identity_id) is not int or identity_id < 1:
            raise RepairError("enslaver identity timestamp projection returned an invalid key")
        if identity_id in seen_ids:
            raise RepairError("enslaver identity timestamp projection returned duplicate keys")
        seen_ids.add(identity_id)
        entries.append(
            {
                "id": identity_id,
                "last_updated": normalize_enslaver_identity_timestamp(last_updated),
            }
        )
    entries.sort(key=lambda entry: entry["id"])
    return len(entries), sha256_bytes(canonical_json(entries).encode())


def verify_enslaver_cache_projection(
    cursor: Any,
    assertion: dict[str, Any],
    require_postimage: bool,
) -> list[dict[str, Any]]:
    projections = validated_enslaver_cache_projections(assertion)
    identity_timestamps = validated_enslaver_identity_timestamps(assertion)
    if not require_postimage:
        evidence = [
            {
                "kind": "enslaver_cache_projection",
                "projection": projection["name"],
                "status": "pending",
                "expectedCount": projection["expected_count"],
                "expectedSha256": projection["expected_sha256"],
                "passed": True,
            }
            for projection in projections
        ]
        evidence.append(
            {
                "kind": "enslaver_cache_projection",
                "projection": "identity_timestamps",
                "status": "pending",
                "expectedCount": identity_timestamps["expected_count"],
                "expectedSha256": identity_timestamps["expected_sha256"],
                "passed": True,
            }
        )
        return evidence

    evidence: list[dict[str, Any]] = []
    for projection in projections:
        name = projection["name"]
        definition = ENSLAVER_CACHE_PROJECTIONS[name]
        graph_pairs = fetch_enslaver_cache_pairs(
            cursor,
            definition["graph_sql"],
            f"enslaver {name} graph projection",
        )
        cache_pairs = fetch_enslaver_cache_pairs(
            cursor,
            definition["cache_sql"],
            f"enslaver {name} cache projection",
        )
        graph_count, graph_sha256 = enslaver_cache_projection_digest(
            graph_pairs, definition["right_column"]
        )
        cache_count, cache_sha256 = enslaver_cache_projection_digest(
            cache_pairs, definition["right_column"]
        )
        expected_count = projection["expected_count"]
        expected_sha256 = projection["expected_sha256"]
        if graph_count != expected_count or graph_sha256 != expected_sha256:
            raise RepairError(
                "enslaver cache graph projection disagrees with approved expectation"
            )
        missing_count = len(graph_pairs - cache_pairs)
        stale_count = len(cache_pairs - graph_pairs)
        if (
            missing_count != 0
            or stale_count != 0
            or cache_count != expected_count
            or cache_sha256 != expected_sha256
        ):
            raise RepairError(
                "enslaver cache projection does not match the repaired graph"
            )
        evidence.append(
            {
                "kind": "enslaver_cache_projection",
                "projection": name,
                "status": "verified",
                "count": cache_count,
                "sha256": cache_sha256,
                "missingCount": missing_count,
                "staleCount": stale_count,
                "passed": True,
            }
        )
    timestamp_count, timestamp_sha256 = enslaver_identity_timestamp_digest(cursor)
    if (
        timestamp_count != identity_timestamps["expected_count"]
        or timestamp_sha256 != identity_timestamps["expected_sha256"]
    ):
        raise RepairError(
            "enslaver identity timestamp projection disagrees with approved expectation"
        )
    evidence.append(
        {
            "kind": "enslaver_cache_projection",
            "projection": "identity_timestamps",
            "status": "verified",
            "count": timestamp_count,
            "sha256": timestamp_sha256,
            "passed": True,
        }
    )
    return evidence


def verify_business_assertions(
    cursor: Any,
    bundles: Sequence[RepairBundle],
    require_postimage: bool,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for bundle in bundles:
        verification = require_mapping(
            bundle.descriptor.get("verification"), "repair verification"
        )
        assertions = verification.get("business_assertions")
        if not isinstance(assertions, list) or not assertions:
            raise RepairError("repair has no business assertions")
        if any(
            assertion.get("kind") == "all_actual_date_differences"
            for assertion in assertions
        ):
            evidence.extend(
                verify_duration_assertions(
                    cursor, bundle, assertions, require_postimage
                )
            )
        for assertion_value in assertions:
            assertion = require_mapping(assertion_value, "business assertion")
            kind = assertion.get("kind")
            if kind in {"all_actual_date_differences", "actual_date_difference"}:
                continue
            if kind == "voyage_enslaver_role":
                if not require_postimage:
                    evidence.append(
                        {"kind": kind, "status": "pending", "passed": True}
                    )
                    continue
                verify_voyage_enslaver_role(cursor, assertion)
            elif kind == "foreign_key_value":
                table = assertion.get("table")
                row_id = assertion.get("id")
                name = assertion.get("name")
                if table != "voyage_nationality" or not isinstance(row_id, int):
                    raise RepairError("foreign-key assertion is invalid")
                cursor.execute(
                    f"SELECT name FROM {quote_identifier(table)} WHERE id = %s",
                    [row_id],
                )
                row = cursor.fetchone()
                if row is None or normalize_value(row[0]) != name:
                    raise RepairError("foreign-key lookup assertion failed")
            elif kind == "one_new_source_per_new_connection":
                verify_source_pairing(bundle, assertion.get("expected_count"))
            elif kind == "no_external_network_calls":
                pass
            elif kind == "enslaver_cache_projection":
                evidence.extend(
                    verify_enslaver_cache_projection(cursor, assertion, require_postimage)
                )
                continue
            else:
                raise RepairError("repair contains an unsupported business assertion")
            evidence.append({"kind": kind, "passed": True})
    return evidence


def operation_signature(operation: dict[str, Any]) -> tuple[Any, ...]:
    action = operation["action"]
    table = operation["table"]
    if action == "insert":
        columns = tuple(sorted(set(operation["key"]) | set(operation["after"])))
        return action, table, columns
    predicates = dict(operation["key"])
    predicates.update(operation["before"])
    predicate_shape = tuple(
        (column, predicates[column] is None) for column in sorted(predicates)
    )
    if action == "update":
        return action, table, tuple(sorted(operation["after"])), predicate_shape
    return action, table, predicate_shape


def operation_statement_and_parameters(
    operation: dict[str, Any]
) -> tuple[str, list[Any]]:
    table = quote_identifier(operation["table"])
    key = operation["key"]
    before = operation["before"]
    after = operation["after"]
    if operation["action"] == "insert":
        values = dict(key)
        values.update(after)
        columns = sorted(values)
        statement = (
            f"INSERT INTO {table} ("
            + ",".join(quote_identifier(column) for column in columns)
            + ") VALUES ("
            + ",".join(["%s"] * len(columns))
            + ")"
        )
        parameters = [database_parameter(values[column]) for column in columns]
    elif operation["action"] == "update":
        columns = sorted(after)
        predicates = dict(key)
        predicates.update(before)
        where, where_parameters = where_clause(predicates)
        statement = (
            f"UPDATE {table} SET "
            + ",".join(f"{quote_identifier(column)} = %s" for column in columns)
            + f" WHERE {where}"
        )
        parameters = [database_parameter(after[column]) for column in columns]
        parameters.extend(where_parameters)
    else:
        predicates = dict(key)
        predicates.update(before)
        where, parameters = where_clause(predicates)
        statement = f"DELETE FROM {table} WHERE {where}"
    return statement, parameters


def apply_operation_batch(
    cursor: Any, operations: Sequence[dict[str, Any]]
) -> None:
    if not operations:
        return
    statements_and_parameters = [
        operation_statement_and_parameters(operation) for operation in operations
    ]
    statements = {item[0] for item in statements_and_parameters}
    if len(statements) != 1:
        raise RepairError("repair batch contains incompatible operations")
    statement = statements.pop()
    cursor.executemany(
        statement,
        [item[1] for item in statements_and_parameters],
    )
    if cursor.rowcount != len(operations):
        raise RepairError("guarded repair batch did not affect every expected row")


def apply_operation(cursor: Any, operation: dict[str, Any]) -> None:
    apply_operation_batch(cursor, [operation])


def apply_operations(cursor: Any, bundles: Iterable[RepairBundle]) -> None:
    for bundle in bundles:
        for _, compatible in groupby(bundle.operations, key=operation_signature):
            operations = list(compatible)
            for operation_batch in batched(operations):
                apply_operation_batch(cursor, operation_batch)


REFERENCE_GUARD_CONTRACT = {
    "information_schema_incoming_foreign_keys": "required",
    "delete_policy": "abort-on-unmanifested-reference",
    "insert_policy": "abort-on-key-conflict",
    "update_policy": "exact-postimage-required",
    "foreign_key_checks": "required",
}
APPROVAL_ID = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[a-z0-9-]+-production-v[1-9][0-9]*$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROMOTION_ID = re.compile(r"^promotion-[0-9a-f]{20}$")
EVIDENCE_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
EVIDENCE_KEY = re.compile(r"^receipts/[A-Za-z0-9._:/-]+\.json$")
VERSION_ID = re.compile(r"^[A-Za-z0-9._+=/-]{1,1024}$")
DIGEST_PINNED_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}$"
)


def required_reference_guard(bundles: Sequence[RepairBundle]) -> bool:
    inverse_flags = [bundle.descriptor.get("inverse") is not None for bundle in bundles]
    guard_flags = [
        bundle.descriptor.get("referential_integrity") is not None
        for bundle in bundles
    ]
    if any(inverse_flags) and not all(inverse_flags):
        raise RepairError("repair set mixes forward and inverse bundles")
    if any(guard_flags) and not all(guard_flags):
        raise RepairError("repair set mixes guarded and unguarded bundles")
    if any(inverse_flags) != any(guard_flags):
        raise RepairError("inverse repair set lacks mandatory reference guards")
    if not any(inverse_flags):
        return False
    for bundle in bundles:
        inverse = require_mapping(bundle.descriptor["inverse"], "inverse contract")
        if inverse.get("reverse_operation_order") is not True:
            raise RepairError("inverse repair does not reverse operation order")
        contract = require_mapping(
            bundle.descriptor["referential_integrity"],
            "referential integrity contract",
        )
        if contract != REFERENCE_GUARD_CONTRACT:
            raise RepairError("referential integrity contract is invalid")
    return True


def incoming_foreign_keys(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        "SELECT k.CONSTRAINT_NAME,k.TABLE_NAME,k.COLUMN_NAME,"
        "k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,k.ORDINAL_POSITION,"
        "r.DELETE_RULE FROM information_schema.KEY_COLUMN_USAGE k "
        "JOIN information_schema.REFERENTIAL_CONSTRAINTS r "
        "ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA "
        "AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME "
        "AND r.TABLE_NAME=k.TABLE_NAME "
        "WHERE k.CONSTRAINT_SCHEMA=DATABASE() "
        "AND k.REFERENCED_TABLE_SCHEMA=DATABASE() "
        "AND k.REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY k.REFERENCED_TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION"
    )
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (
        constraint,
        child_table,
        child_column,
        parent_table,
        parent_column,
        ordinal,
        delete_rule,
    ) in cursor.fetchall():
        for identifier in (
            child_table,
            child_column,
            parent_table,
            parent_column,
        ):
            quote_identifier(str(identifier))
        if delete_rule not in {"CASCADE", "NO ACTION", "RESTRICT", "SET NULL"}:
            raise RepairError("incoming foreign-key delete rule is invalid")
        marker = (str(constraint), str(child_table), str(parent_table))
        entry = grouped.setdefault(
            marker,
            {
                "constraint": str(constraint),
                "child_table": str(child_table),
                "parent_table": str(parent_table),
                "child_columns": [],
                "parent_columns": [],
                "ordinals": [],
                "delete_rule": str(delete_rule),
            },
        )
        if entry["delete_rule"] != delete_rule:
            raise RepairError("incoming foreign-key delete rules disagree")
        entry["child_columns"].append(str(child_column))
        entry["parent_columns"].append(str(parent_column))
        entry["ordinals"].append(int(ordinal))
    result = []
    for entry in grouped.values():
        if entry["ordinals"] != list(range(1, len(entry["ordinals"]) + 1)):
            raise RepairError("incoming foreign-key metadata is not contiguous")
        result.append(entry)
    return sorted(
        result,
        key=lambda value: (
            value["parent_table"],
            value["child_table"],
            value["constraint"],
        ),
    )


def global_delete_schedule(
    bundles: Sequence[RepairBundle],
) -> tuple[
    dict[str, list[tuple[int, dict[str, Any]]]],
    dict[str, dict[tuple[str, ...], dict[str, int]]],
]:
    operations_by_table: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    keys_by_table: dict[
        str, dict[tuple[str, ...], dict[str, int]]
    ] = defaultdict(lambda: defaultdict(dict))
    position = 0
    for bundle in bundles:
        for operation in bundle.operations:
            position += 1
            if operation["action"] != "delete":
                continue
            table = operation["table"]
            columns = tuple(sorted(operation["key"]))
            key = normalized_key(operation["key"], columns)
            if key in keys_by_table[table][columns]:
                raise RepairError("inverse manifest repeats a delete key")
            keys_by_table[table][columns][key] = position
            operations_by_table[table].append((position, operation))
    return operations_by_table, keys_by_table


def scheduled_child_delete_position(
    row: dict[str, Any],
    signatures: dict[tuple[str, ...], dict[str, int]],
) -> int | None:
    matches: list[int] = []
    for columns, scheduled in signatures.items():
        if any(column not in row for column in columns):
            continue
        position = scheduled.get(normalized_key(row, columns))
        if position is not None:
            matches.append(position)
    if len(matches) > 1:
        raise RepairError("incoming row matches multiple inverse deletes")
    return matches[0] if matches else None


def tuple_predicate(
    columns: Sequence[str], value_count: int
) -> tuple[str, str]:
    if len(columns) == 1:
        expression = quote_identifier(columns[0])
        row_placeholder = "%s"
    else:
        expression = "(" + ",".join(quote_identifier(column) for column in columns) + ")"
        row_placeholder = "(" + ",".join(["%s"] * len(columns)) + ")"
    return expression, ",".join([row_placeholder] * value_count)


def verify_incoming_reference_closure(
    cursor: Any,
    bundles: Sequence[RepairBundle],
    rows: dict[tuple[str, int], dict[str, Any] | None],
    *,
    lock_rows: bool,
) -> dict[str, int | bool]:
    if not required_reference_guard(bundles):
        return {
            "required": False,
            "foreignKeysChecked": 0,
            "parentRowsChecked": 0,
            "childRowsChecked": 0,
        }
    cursor.execute("SELECT @@FOREIGN_KEY_CHECKS")
    foreign_key_checks = cursor.fetchone()
    if not foreign_key_checks or int(foreign_key_checks[0]) != 1:
        raise RepairError("rollback requires FOREIGN_KEY_CHECKS=1")

    delete_operations, scheduled_keys = global_delete_schedule(bundles)
    checked_constraints = 0
    checked_parents = 0
    checked_children = 0
    for foreign_key in incoming_foreign_keys(cursor):
        parent_table = foreign_key["parent_table"]
        parents = delete_operations.get(parent_table, [])
        if not parents:
            continue
        parent_columns = tuple(foreign_key["parent_columns"])
        child_columns = tuple(foreign_key["child_columns"])
        parent_positions: dict[str, int] = {}
        parent_values: list[tuple[Any, ...]] = []
        for position, operation in parents:
            live_row = rows.get(operation_token(operation))
            if live_row is None:
                raise RepairError(
                    "rollback delete guard cannot resolve a live parent row"
                )
            if any(column not in live_row for column in parent_columns):
                raise RepairError(
                    "rollback delete guard cannot resolve a referenced parent key"
                )
            values = tuple(live_row[column] for column in parent_columns)
            marker = canonical_json([normalize_value(value) for value in values])
            if marker in parent_positions:
                raise RepairError(
                    "rollback delete guard found duplicate referenced parent keys"
                )
            parent_positions[marker] = position
            parent_values.append(values)

        child_table = foreign_key["child_table"]
        child_signatures = scheduled_keys.get(child_table, {})
        selected_columns = sorted(
            set(child_columns)
            | {
                column
                for signature in child_signatures
                for column in signature
            }
        )
        if not selected_columns:
            raise RepairError("rollback delete guard has no child-row identity")
        for value_batch in batched(parent_values):
            expression, placeholders = tuple_predicate(
                parent_columns, len(value_batch)
            )
            parameters = [
                database_parameter(value)
                for values in value_batch
                for value in values
            ]
            parent_statement = (
                "SELECT "
                + ",".join(quote_identifier(column) for column in parent_columns)
                + f" FROM {quote_identifier(parent_table)} "
                + f"WHERE {expression} IN ({placeholders})"
            )
            if lock_rows:
                parent_statement += " FOR UPDATE"
            cursor.execute(parent_statement, parameters)
            locked_parent_rows = cursor.fetchall()
            if len(locked_parent_rows) != len(value_batch):
                raise RepairError("rollback delete guard could not lock every parent")
            checked_parents += len(locked_parent_rows)

            child_expression, child_placeholders = tuple_predicate(
                child_columns, len(value_batch)
            )
            child_statement = (
                "SELECT "
                + ",".join(quote_identifier(column) for column in selected_columns)
                + f" FROM {quote_identifier(child_table)} "
                + f"WHERE {child_expression} IN ({child_placeholders})"
            )
            if lock_rows:
                child_statement += " FOR UPDATE"
            cursor.execute(child_statement, parameters)
            for raw_row in cursor.fetchall():
                checked_children += 1
                row = dict(zip(selected_columns, raw_row))
                child_position = scheduled_child_delete_position(
                    row, child_signatures
                )
                parent_marker = canonical_json(
                    [normalize_value(row[column]) for column in child_columns]
                )
                parent_position = parent_positions.get(parent_marker)
                if (
                    child_position is None
                    or parent_position is None
                    or child_position >= parent_position
                ):
                    raise RepairError(
                        "rollback found an incoming reference not deleted earlier "
                        "by the inverse manifest"
                    )
        checked_constraints += 1
    return {
        "required": True,
        "foreignKeysChecked": checked_constraints,
        "parentRowsChecked": checked_parents,
        "childRowsChecked": checked_children,
    }


def authorization_environment() -> dict[str, str]:
    names = {
        "approvalId": "VOYAGES_DB_REPAIR_APPROVAL_ID",
        "approvalSha256": "VOYAGES_DB_REPAIR_APPROVAL_SHA256",
        "forwardSetId": "VOYAGES_DB_REPAIR_FORWARD_SET_ID",
        "forwardSetSha256": "VOYAGES_DB_REPAIR_FORWARD_SET_SHA256",
        "inverseSetId": "VOYAGES_DB_REPAIR_INVERSE_SET_ID",
        "inverseSetSha256": "VOYAGES_DB_REPAIR_INVERSE_SET_SHA256",
        "candidateAcceptanceBucket": "VOYAGES_DB_REPAIR_CANDIDATE_ACCEPTANCE_BUCKET",
        "candidateAcceptanceKey": "VOYAGES_DB_REPAIR_CANDIDATE_ACCEPTANCE_KEY",
        "candidateAcceptanceVersionId": "VOYAGES_DB_REPAIR_CANDIDATE_ACCEPTANCE_VERSION_ID",
        "candidateAcceptanceSha256": "VOYAGES_DB_REPAIR_CANDIDATE_ACCEPTANCE_SHA256",
        "candidateRepairBucket": "VOYAGES_DB_REPAIR_CANDIDATE_RECEIPT_BUCKET",
        "candidateRepairKey": "VOYAGES_DB_REPAIR_CANDIDATE_RECEIPT_KEY",
        "candidateRepairVersionId": "VOYAGES_DB_REPAIR_CANDIDATE_RECEIPT_VERSION_ID",
        "candidateRepairSha256": "VOYAGES_DB_REPAIR_CANDIDATE_RECEIPT_SHA256",
        "promotionId": "VOYAGES_DB_REPAIR_PROMOTION_ID",
        "apiPatchSetSha256": "VOYAGES_DB_REPAIR_API_PATCH_SET_SHA256",
        "apiImage": "VOYAGES_DB_REPAIR_API_IMAGE",
    }
    evidence = {key: os.environ.get(name, "") for key, name in names.items()}
    version = os.environ.get("VOYAGES_RELEASE_PROVENANCE_VERSION", "3")
    if version not in {"3", "4"}:
        raise RepairError("unsupported production repair provenance version")
    if version == "4":
        if evidence.pop("apiPatchSetSha256"):
            raise RepairError("upstream repair provenance cannot contain a patch digest")
        evidence["provenanceVersion"] = version
    if any(not value for value in evidence.values()):
        raise RepairError("production repair authorization is incomplete")
    return evidence


def validate_receipt_reference(
    evidence: dict[str, str], prefix: str
) -> dict[str, str]:
    bucket = evidence[f"{prefix}Bucket"]
    key = evidence[f"{prefix}Key"]
    version = evidence[f"{prefix}VersionId"]
    digest = evidence[f"{prefix}Sha256"]
    if (
        EVIDENCE_BUCKET.fullmatch(bucket) is None
        or EVIDENCE_KEY.fullmatch(key) is None
        or ".." in key.split("/")
        or VERSION_ID.fullmatch(version) is None
        or version == "null"
        or SHA256.fullmatch(digest) is None
    ):
        raise RepairError("production repair authorization has an invalid receipt")
    return {
        "bucket": bucket,
        "key": key,
        "versionId": version,
        "sha256": digest,
    }


def expected_promotion_id(
    evidence: dict[str, str],
    acceptance: dict[str, str],
    final_repair: dict[str, str],
) -> str:
    seed = "|".join(
        [
            evidence["approvalId"],
            evidence["approvalSha256"],
            evidence["forwardSetId"],
            evidence["forwardSetSha256"],
            evidence["inverseSetId"],
            evidence["inverseSetSha256"],
            acceptance["bucket"],
            acceptance["key"],
            acceptance["versionId"],
            acceptance["sha256"],
            final_repair["bucket"],
            final_repair["key"],
            final_repair["versionId"],
            final_repair["sha256"],
            evidence.get("apiPatchSetSha256", ""),
            evidence["apiImage"],
        ]
    )
    return "promotion-" + hashlib.sha256(seed.encode()).hexdigest()[:20]


def repair_set_artifact_digest(repair_root: Path, repair_set: str) -> str:
    if REPAIR_ID.fullmatch(repair_set) is None:
        raise RepairError("production authorization references an invalid repair set")
    set_path = repair_root / "sets" / f"{repair_set}.yaml"
    descriptor = load_yaml(set_path)
    if descriptor.get("id") != repair_set:
        raise RepairError("production authorization repair-set ID mismatch")
    repair_ids = descriptor.get("repairs")
    if (
        not isinstance(repair_ids, list)
        or not repair_ids
        or len(repair_ids) != len(set(repair_ids))
    ):
        raise RepairError("production authorization repair set is invalid")
    repairs = []
    for repair_id in repair_ids:
        if not isinstance(repair_id, str) or REPAIR_ID.fullmatch(repair_id) is None:
            raise RepairError("production authorization repair ID is invalid")
        directory = repair_root / repair_id
        descriptor_path = directory / "repair.yaml"
        repair_descriptor = load_yaml(descriptor_path)
        if repair_descriptor.get("id") != repair_id:
            raise RepairError("production authorization repair descriptor mismatch")
        manifest_sha256 = sha256_file(directory / "manifest.jsonl")
        if repair_descriptor.get("manifest_sha256") != manifest_sha256:
            raise RepairError("production authorization manifest digest mismatch")
        repairs.append(
            {
                "descriptor_sha256": sha256_file(descriptor_path),
                "id": repair_id,
                "manifest_sha256": manifest_sha256,
            }
        )
    payload = {
        "repair_set": repair_set,
        "repair_set_descriptor_sha256": sha256_file(set_path),
        "repairs": repairs,
        "schema_version": 1,
    }
    return sha256_bytes(canonical_json(payload).encode())


def production_authorization(
    repair_root: Path,
    repair_set: str,
    repair_set_sha256: str,
    target: str,
) -> dict[str, Any] | None:
    if target != "production":
        return None
    evidence = authorization_environment()
    digest_fields = (
        "approvalSha256",
        "forwardSetSha256",
        "inverseSetSha256",
    ) + (("apiPatchSetSha256",) if evidence.get("provenanceVersion") != "4" else ())
    if any(SHA256.fullmatch(evidence[field]) is None for field in digest_fields):
        raise RepairError("production repair authorization has an invalid digest")
    if (
        APPROVAL_ID.fullmatch(evidence["approvalId"]) is None
        or REPAIR_ID.fullmatch(evidence["forwardSetId"]) is None
        or REPAIR_ID.fullmatch(evidence["inverseSetId"]) is None
        or PROMOTION_ID.fullmatch(evidence["promotionId"]) is None
        or DIGEST_PINNED_IMAGE.fullmatch(evidence["apiImage"]) is None
    ):
        raise RepairError("production repair authorization has an invalid identity")
    runtime_patch_digest = os.environ.get("VOYAGES_API_PATCH_SET_SHA256", "")
    runtime_image = os.environ.get("VOYAGES_API_IMAGE", "")
    if (
        runtime_patch_digest != evidence.get("apiPatchSetSha256", "")
        or runtime_image != evidence["apiImage"]
    ):
        raise RepairError("production repair image provenance does not match authorization")

    approval_path = repair_root / "approvals" / f"{evidence['approvalId']}.yaml"
    approval = load_yaml(approval_path)
    if sha256_file(approval_path) != evidence["approvalSha256"]:
        raise RepairError("production approval digest does not match the image")
    if (
        approval.get("status") != "approved"
        or approval.get("allowed_production_database") != PRODUCTION_DATABASE
    ):
        raise RepairError("production approval is absent or targets another database")
    forward = require_mapping(approval.get("forward"), "approval forward set")
    inverse = require_mapping(approval.get("inverse"), "approval inverse set")
    if (
        forward.get("repair_set_id") != evidence["forwardSetId"]
        or forward.get("repair_set_sha256") != evidence["forwardSetSha256"]
        or inverse.get("repair_set_id") != evidence["inverseSetId"]
        or inverse.get("repair_set_sha256") != evidence["inverseSetSha256"]
        or inverse.get("reviewed") is not True
    ):
        raise RepairError("production authorization differs from approved repair sets")
    approved_sets = {
        evidence["forwardSetId"]: evidence["forwardSetSha256"],
        evidence["inverseSetId"]: evidence["inverseSetSha256"],
    }
    if approved_sets.get(repair_set) != repair_set_sha256:
        raise RepairError(
            "selected production repair is not the approved forward or inverse set"
        )
    for approved_set, approved_digest in approved_sets.items():
        if repair_set_artifact_digest(repair_root, approved_set) != approved_digest:
            raise RepairError(
                "production authorization repair-set artifact digest mismatch"
            )
    acceptance = validate_receipt_reference(evidence, "candidateAcceptance")
    final_repair = validate_receipt_reference(evidence, "candidateRepair")
    if expected_promotion_id(evidence, acceptance, final_repair) != evidence[
        "promotionId"
    ]:
        raise RepairError("production promotion identity does not match authorization")
    return {
        "approvalId": evidence["approvalId"],
        "approvalSha256": evidence["approvalSha256"],
        "forwardSetId": evidence["forwardSetId"],
        "forwardSetSha256": evidence["forwardSetSha256"],
        "inverseSetId": evidence["inverseSetId"],
        "inverseSetSha256": evidence["inverseSetSha256"],
        "candidateAcceptanceReceipt": acceptance,
        "candidateRepairReceipt": final_repair,
        "promotionId": evidence["promotionId"],
        **({"provenanceVersion": 4} if evidence.get("provenanceVersion") == "4" else
           {"apiPatchSetSha256": evidence["apiPatchSetSha256"]}),
        "apiImage": evidence["apiImage"],
    }


def verify_database_target(
    cursor: Any,
    target: str,
    expected_database: str,
    expected_user: str | None,
    require_peer_verified_tls: bool,
) -> tuple[str, str, str, str, bool, str]:
    cursor.execute(
        "SHOW SESSION STATUS WHERE Variable_name IN ('Ssl_cipher','Ssl_version')"
    )
    tls_status = {str(name): str(value) for name, value in cursor.fetchall()}
    tls_cipher = tls_status.get("Ssl_cipher", "")
    tls_version = tls_status.get("Ssl_version", "")
    tls_peer_verified = False
    tls_ca_bundle_sha256 = ""
    if require_peer_verified_tls:
        if not tls_cipher or not tls_version:
            raise RepairError(
                "repair requires peer-verified encrypted database transport"
            )
        ssl_options = connection.settings_dict.get("OPTIONS", {}).get("ssl", {})
        if (
            os.environ.get("MYSQL_SSL_REQUIRED", "").lower() != "true"
            or os.environ.get("MYSQL_CLIENT_TLS_FLAG") != "--ssl-mode=REQUIRED"
            or os.environ.get("MYSQL_SSL_CA_PATH") != PINNED_RDS_CA_PATH
            or connection.settings_dict.get("OPTIONS", {}).get("read_default_file")
            != PINNED_RDS_CLIENT_CONFIG
            or connection.settings_dict.get("OPTIONS", {}).get("ssl_mode")
            != "VERIFY_IDENTITY"
            or ssl_options.get("ca") != PINNED_RDS_CA_PATH
            or not Path(PINNED_RDS_CA_PATH).is_file()
            or sha256_file(Path(PINNED_RDS_CA_PATH)) != PINNED_RDS_CA_SHA256
            or not Path(PINNED_RDS_CLIENT_CONFIG).is_file()
            or sha256_file(Path(PINNED_RDS_CLIENT_CONFIG))
            != PINNED_RDS_CLIENT_CONFIG_SHA256
        ):
            raise RepairError(
                "repair requires the pinned peer-verified RDS TLS client profile"
            )
        tls_peer_verified = True
        tls_ca_bundle_sha256 = PINNED_RDS_CA_SHA256
    elif target == "production":
        raise RepairError("production repair requires peer-verified RDS TLS")
    cursor.execute("SELECT DATABASE(), CURRENT_USER()")
    database_name, current_user = cursor.fetchone()
    if database_name != expected_database:
        raise RepairError("database identity does not match the guarded target")
    if expected_user and current_user.split("@", 1)[0] != expected_user:
        raise RepairError("database principal does not match the guarded target")
    if target == "candidate":
        if not CANDIDATE_DATABASE.fullmatch(database_name):
            raise RepairError("candidate repair refuses a non-candidate database")
    elif target == "production":
        enabled = os.environ.get("VOYAGES_ENABLE_PRODUCTION_REPAIR") == "1"
        if database_name != PRODUCTION_DATABASE or not enabled:
            raise RepairError("production repair is not enabled by promotion")
    else:
        raise RepairError("unknown repair target")
    return (
        database_name,
        current_user,
        tls_cipher,
        tls_version,
        tls_peer_verified,
        tls_ca_bundle_sha256,
    )


def verify_database_compatibility(
    cursor: Any, bundles: Sequence[RepairBundle]
) -> str:
    expected_versions: set[str] = set()
    for bundle in bundles:
        compatibility = require_mapping(
            bundle.descriptor.get("compatibility"), "repair compatibility"
        )
        if compatibility.get("engine") != "MariaDB":
            raise RepairError("repair requires an unsupported database engine")
        major_minor = compatibility.get("major_minor")
        if not isinstance(major_minor, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", major_minor):
            raise RepairError("repair has an invalid database version requirement")
        expected_versions.add(major_minor)
    if len(expected_versions) != 1:
        raise RepairError("repair set has inconsistent database requirements")
    cursor.execute("SELECT VERSION()")
    actual_version = str(cursor.fetchone()[0])
    expected_version = expected_versions.pop()
    if "MariaDB" not in actual_version or not actual_version.startswith(
        expected_version + "."
    ):
        raise RepairError("database engine version is incompatible with repair")
    expected_tables = sorted(
        {
            table
            for bundle in bundles
            for table in bundle.descriptor["allowed_tables"]
        }
    )
    placeholders = ",".join(["%s"] * len(expected_tables))
    cursor.execute(
        "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        f"AND TABLE_NAME IN ({placeholders})",
        expected_tables,
    )
    table_engines = {table: engine for table, engine in cursor.fetchall()}
    if set(table_engines) != set(expected_tables):
        raise RepairError("repair target is missing an allowed table")
    if any(engine != "InnoDB" for engine in table_engines.values()):
        raise RepairError("repair set requires InnoDB tables")
    return actual_version


def write_receipt(
    receipt: dict[str, Any],
    receipt_dir: Path,
    bucket: str | None,
    prefix: str,
    kms_key_id: str | None,
) -> tuple[Path, dict[str, str] | None]:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    payload = (canonical_json(receipt) + "\n").encode()
    filename = f"{receipt['executionId']}.json"
    path = receipt_dir / filename
    path.write_bytes(payload)
    if not bucket:
        return path, None
    if not kms_key_id:
        raise RepairError("receipt bucket requires a KMS key")
    key = f"{prefix.strip('/')}/{filename}"
    checksum = hashlib.sha256(payload).digest()
    result = boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=kms_key_id,
        ChecksumSHA256=base64.b64encode(checksum).decode(),
        Metadata={"sha256": checksum.hex()},
    )
    return path, {
        "bucket": bucket,
        "key": key,
        "versionId": result.get("VersionId", ""),
        "sha256": checksum.hex(),
    }


class Command(BaseCommand):
    help = "Check, transactionally apply, or verify an immutable Voyages data repair set."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--repair-set", required=True)
        parser.add_argument(
            "--repair-root",
            default=os.environ.get(
                "VOYAGES_DB_REPAIR_ROOT", "/srv/voyages-api/db/repairs"
            ),
        )
        parser.add_argument("--target", choices=("candidate", "production"), required=True)
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--expected-user")
        parser.add_argument("--require-peer-verified-tls", action="store_true")
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("--check", action="store_true")
        modes.add_argument("--apply", action="store_true")
        modes.add_argument("--verify", action="store_true")
        parser.add_argument(
            "--receipt-dir",
            default=os.environ.get(
                "VOYAGES_DB_REPAIR_RECEIPT_DIR", "/tmp/voyages-db-repairs"
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        mode = next(name for name in ("check", "apply", "verify") if options[name])
        started = dt.datetime.now(dt.timezone.utc)
        execution_id = (
            f"{options['repair_set']}-{mode}-"
            f"{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
        )
        receipt: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "executionId": execution_id,
            "repairSet": options["repair_set"],
            "mode": mode,
            "target": options["target"],
            "startedAt": started.isoformat(),
            "result": "failed",
            "noOp": False,
        }
        receipt_path: Path | None = None
        try:
            repair_root = Path(options["repair_root"])
            _, bundles, repair_set_sha = load_repair_set(
                repair_root, options["repair_set"]
            )
            authorization = production_authorization(
                repair_root,
                options["repair_set"],
                repair_set_sha,
                options["target"],
            )
            if authorization is not None:
                receipt["productionAuthorization"] = authorization
            for bundle in bundles:
                validate_projection_digests(bundle)
            receipt["repairSetSha256"] = repair_set_sha
            receipt["repairs"] = [
                {
                    "id": bundle.repair_id,
                    "manifestSha256": bundle.manifest_sha256,
                    "operationCount": len(bundle.operations),
                }
                for bundle in bundles
            ]
            receipt["operationCount"] = sum(
                len(bundle.operations) for bundle in bundles
            )
            with connection.cursor() as cursor:
                (
                    database_name,
                    current_user,
                    tls_cipher,
                    tls_version,
                    tls_peer_verified,
                    tls_ca_bundle_sha256,
                ) = verify_database_target(
                    cursor,
                    options["target"],
                    options["expected_database"],
                    options.get("expected_user"),
                    options["require_peer_verified_tls"],
                )
                receipt["database"] = database_name
                receipt["principal"] = current_user
                receipt["tlsCipher"] = tls_cipher
                receipt["tlsVersion"] = tls_version
                receipt["tlsPeerVerified"] = tls_peer_verified
                receipt["tlsCABundleSHA256"] = tls_ca_bundle_sha256
                receipt["databaseEngineVersion"] = verify_database_compatibility(
                    cursor, bundles
                )
                lock_name = f"voyages-data-repair:{options['repair_set']}"
                lock_acquired = False
                if mode == "apply":
                    cursor.execute("SELECT GET_LOCK(%s, 30)", [lock_name])
                    lock_acquired = cursor.fetchone()[0] == 1
                    if not lock_acquired:
                        raise RepairError("repair advisory lock is unavailable")
                try:
                    states, rows = inspect_operations(cursor, bundles)
                    counts = {state: states.count(state) for state in set(states)}
                    receipt["preconditionStates"] = counts
                    if "conflict" in counts:
                        raise RepairError("repair preconditions conflict with live data")
                    all_pending = counts == {"pending": len(states)}
                    all_applied = counts == {"applied": len(states)}
                    if not (all_pending or all_applied):
                        raise RepairError("repair set is partially applied")
                    image_name = "before" if all_pending else "after"
                    if all_pending:
                        receipt["incomingReferenceGuard"] = (
                            verify_incoming_reference_closure(
                                cursor, bundles, rows, lock_rows=False
                            )
                        )
                    receipt["liveImageSha256"] = live_digest_evidence(
                        bundles, image_name, rows
                    )
                    if receipt["liveImageSha256"] != expected_digest_evidence(
                        bundles, image_name
                    ):
                        raise RepairError("repair full-set digest does not match live data")
                    if mode == "check":
                        receipt["sentinels"] = sentinel_evidence(
                            bundles, image_name, rows
                        )
                        receipt["businessAssertions"] = verify_business_assertions(
                            cursor, bundles, all_applied
                        )
                        receipt["result"] = "ready" if all_pending else "already-applied"
                        receipt["noOp"] = all_applied
                    elif mode == "verify":
                        if not all_applied:
                            raise RepairError("repair verification found pending operations")
                        receipt["sentinels"] = sentinel_evidence(
                            bundles, "after", rows
                        )
                        receipt["businessAssertions"] = verify_business_assertions(
                            cursor, bundles, True
                        )
                        receipt["result"] = "verified"
                    elif all_applied:
                        receipt["sentinels"] = sentinel_evidence(
                            bundles, "after", rows
                        )
                        receipt["businessAssertions"] = verify_business_assertions(
                            cursor, bundles, True
                        )
                        receipt["result"] = "no-op"
                        receipt["noOp"] = True
                    else:
                        with transaction.atomic():
                            states, locked_rows = inspect_operations(cursor, bundles)
                            if states != ["pending"] * len(states):
                                raise RepairError(
                                    "repair preconditions changed before transaction"
                                )
                            receipt["incomingReferenceGuardRecheck"] = (
                                verify_incoming_reference_closure(
                                    cursor, bundles, locked_rows, lock_rows=True
                                )
                            )
                            apply_operations(cursor, bundles)
                            post_states, post_rows = inspect_operations(
                                cursor, bundles
                            )
                            if post_states != ["applied"] * len(post_states):
                                raise RepairError("repair postconditions failed")
                            receipt["liveImageSha256"] = live_digest_evidence(
                                bundles, "after", post_rows
                            )
                            if receipt[
                                "liveImageSha256"
                            ] != expected_digest_evidence(bundles, "after"):
                                raise RepairError(
                                    "repair postimage digest does not match live data"
                                )
                            receipt["sentinels"] = sentinel_evidence(
                                bundles, "after", post_rows
                            )
                            receipt["businessAssertions"] = verify_business_assertions(
                                cursor, bundles, True
                            )
                        receipt["result"] = "applied"
                finally:
                    if lock_acquired:
                        cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])
        except Exception as exc:
            receipt["error"] = (
                str(exc) if isinstance(exc, RepairError) else "unexpected repair failure"
            )
            failure = exc
        else:
            failure = None
        receipt["finishedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            receipt_path, object_ref = write_receipt(
                receipt,
                Path(options["receipt_dir"]),
                os.environ.get("VOYAGES_DB_REPAIR_RECEIPT_BUCKET"),
                os.environ.get("VOYAGES_DB_REPAIR_RECEIPT_PREFIX", "receipts"),
                os.environ.get("VOYAGES_DB_REPAIR_RECEIPT_KMS_KEY_ARN"),
            )
            if object_ref:
                self.stdout.write(canonical_json({"receipt": object_ref}))
        except Exception as receipt_exc:
            if failure is None:
                failure = receipt_exc
                receipt["result"] = "failed"
                receipt["error"] = "unable to persist repair receipt"
        if receipt_path:
            self.stdout.write(f"receipt={receipt_path}")
        if failure is not None:
            if isinstance(failure, RepairError):
                raise CommandError(str(failure)) from failure
            raise CommandError("unexpected repair failure") from failure
        self.stdout.write(self.style.SUCCESS(receipt["result"]))
