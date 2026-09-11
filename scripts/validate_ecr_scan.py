"""Fail-closed validation for the approved ECR CRITICAL/HIGH exceptions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA_VERSION = 1
EXPECTED_EXCEPTION_FIELDS = {
    "cve",
    "severity",
    "package",
    "version",
    "rationale",
    "source",
    "review_by",
}
EXPECTED_SEVERITIES = {"CRITICAL", "HIGH"}
REPORT_ONLY_SEVERITIES = {"MEDIUM", "LOW"}
CVE_PATTERN = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
PLATFORM_PATTERN = re.compile(r"linux/(?:amd64|arm64|386|ppc64le|s390x)")
FROM_PATTERN = re.compile(
    r"FROM(?:\s+--[A-Za-z0-9][A-Za-z0-9_.=-]*)*\s+([^\s]+)(?:\s+AS\s+[A-Za-z0-9][A-Za-z0-9_.-]*)?\s*\Z",
    re.IGNORECASE,
)
RUNTIME_IMAGE_PATTERN = re.compile(r"([^@\s$]+)@(sha256:[0-9a-f]{64})\Z")
DEBIAN_TRACKER_PATTERN = re.compile(
    r"https://security-tracker\.debian\.org/tracker/(CVE-[0-9]{4}-[0-9]{4,})"
)


class PolicyError(ValueError):
    """Raised when policy or scan data is unsafe or inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, PolicyError) as exc:
        raise PolicyError(f"unable to load {path}: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyError(message)


def _nonempty_text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and value.strip() == value and value != "", f"invalid {label}")
    _require("\n" not in value and "\r" not in value and "\x00" not in value, f"invalid {label}")
    return value


def _runtime_base_from_dockerfile(dockerfile_path: Path) -> tuple[str, str]:
    try:
        lines = dockerfile_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise PolicyError(f"unable to read Dockerfile {dockerfile_path}: {exc}") from exc

    from_lines = [line.strip() for line in lines if line.lstrip().upper().startswith("FROM")]
    _require(from_lines, "Dockerfile has no FROM instruction")
    runtime_from = from_lines[-1]
    _require("\\" not in runtime_from, "runtime FROM instruction is ambiguous")
    match = FROM_PATTERN.fullmatch(runtime_from)
    _require(match is not None, "runtime FROM instruction is malformed or ambiguous")
    image_reference = match.group(1)
    _require("$" not in image_reference, "runtime FROM image must be literal")
    image_match = RUNTIME_IMAGE_PATTERN.fullmatch(image_reference)
    _require(image_match is not None, "runtime FROM image must be sha256-pinned")
    return image_match.group(1), image_match.group(2)


def _validate_allowlist(
    policy: Any,
    *,
    expected_platform: str,
    dockerfile_path: Path,
    today: date,
) -> dict[str, tuple[str, str, str]]:
    _require(isinstance(policy, dict), "allowlist root must be an object")
    _require(
        set(policy) == {"schema_version", "image", "exceptions"},
        "allowlist root fields are invalid",
    )
    _require(policy["schema_version"] == EXPECTED_SCHEMA_VERSION, "unsupported allowlist schema")

    image = policy["image"]
    _require(isinstance(image, dict), "allowlist image must be an object")
    _require(set(image) == {"platform", "python_runtime_base"}, "allowlist image fields are invalid")
    _require(
        isinstance(expected_platform, str) and PLATFORM_PATTERN.fullmatch(expected_platform) is not None,
        "observed image platform is malformed",
    )
    _require(image["platform"] == expected_platform, "allowlist platform does not match Docker target")

    runtime_base = image["python_runtime_base"]
    _require(isinstance(runtime_base, dict), "python runtime base must be an object")
    _require(set(runtime_base) == {"image", "digest"}, "python runtime base fields are invalid")
    digest = runtime_base["digest"]
    _require(isinstance(digest, str), "invalid base image digest")
    _require(DIGEST_PATTERN.fullmatch(digest) is not None, "invalid base image digest")
    observed_base_image, observed_base_digest = _runtime_base_from_dockerfile(dockerfile_path)
    _require(runtime_base["image"] == observed_base_image, "allowlist base image does not match Dockerfile")
    _require(digest == observed_base_digest, "allowlist base digest does not match Dockerfile")

    exceptions = policy["exceptions"]
    _require(isinstance(exceptions, list) and len(exceptions) == 17, "allowlist must contain exactly 17 exceptions")
    by_cve: dict[str, tuple[str, str, str]] = {}

    for index, entry in enumerate(exceptions):
        _require(isinstance(entry, dict), f"allowlist exception {index} must be an object")
        _require(set(entry) == EXPECTED_EXCEPTION_FIELDS, f"allowlist exception {index} fields are invalid")
        cve = entry["cve"]
        _require(isinstance(cve, str) and CVE_PATTERN.fullmatch(cve) is not None, f"invalid CVE at exception {index}")
        _require(cve not in by_cve, f"duplicate allowlist entry: {cve}")
        severity = entry["severity"]
        _require(
            isinstance(severity, str) and severity in EXPECTED_SEVERITIES,
            f"invalid allowlist severity for {cve}",
        )
        package = _nonempty_text(entry["package"], f"package for {cve}")
        version = _nonempty_text(entry["version"], f"version for {cve}")
        rationale = _nonempty_text(entry["rationale"], f"rationale for {cve}")
        _require(len(rationale) <= 1000, f"rationale too long for {cve}")
        source = entry["source"]
        _require(
            isinstance(source, str)
            and DEBIAN_TRACKER_PATTERN.fullmatch(source) is not None
            and source.rsplit("/", 1)[-1] == cve,
            f"invalid Debian tracker URL for {cve}",
        )
        review_by = entry["review_by"]
        try:
            review_date = date.fromisoformat(review_by)
        except (TypeError, ValueError) as exc:
            raise PolicyError(f"invalid review_by for {cve}") from exc
        _require(review_date >= today, f"expired allowlist entry: {cve}")
        by_cve[cve] = (severity, package, version)

    return by_cve


def _package_fields(attributes: Any, cve: str) -> tuple[str, str]:
    _require(isinstance(attributes, list), f"malformed attributes for {cve}")
    values: dict[str, str] = {}
    for attribute in attributes:
        _require(isinstance(attribute, dict), f"malformed attribute for {cve}")
        _require(set(attribute) == {"key", "value"}, f"malformed attribute fields for {cve}")
        key = attribute["key"]
        value = attribute["value"]
        _require(isinstance(key, str) and isinstance(value, str), f"malformed attribute value for {cve}")
        _require(key not in values, f"duplicate scan attribute for {cve}: {key}")
        values[key] = value
    _require("package_name" in values and "package_version" in values, f"package metadata missing for {cve}")
    return _nonempty_text(values["package_name"], f"package for {cve}"), _nonempty_text(values["package_version"], f"version for {cve}")


def _scan_findings(scan: Any) -> tuple[dict[str, tuple[str, str, str]], list[dict[str, str]]]:
    _require(isinstance(scan, dict), "scan root must be an object")
    status = scan.get("imageScanStatus", {}).get("status") if isinstance(scan.get("imageScanStatus"), dict) else None
    _require(status == "COMPLETE", "scan status must be COMPLETE")
    findings_container = scan.get("imageScanFindings")
    _require(isinstance(findings_container, dict), "imageScanFindings must be an object")
    findings = findings_container.get("findings")
    _require(isinstance(findings, list), "scan findings must be a list")

    important: dict[str, tuple[str, str, str]] = {}
    seen_cves: set[str] = set()
    lower: list[dict[str, str]] = []
    for index, finding in enumerate(findings):
        _require(isinstance(finding, dict), f"scan finding {index} must be an object")
        cve = finding.get("name")
        _require(isinstance(cve, str) and CVE_PATTERN.fullmatch(cve) is not None, f"invalid scan CVE at finding {index}")
        severity = finding.get("severity")
        _require(
            isinstance(severity, str)
            and severity in EXPECTED_SEVERITIES | REPORT_ONLY_SEVERITIES,
            f"invalid scan severity for {cve}",
        )
        _require(cve not in seen_cves, f"duplicate scan finding: {cve}")
        seen_cves.add(cve)
        package, version = _package_fields(finding.get("attributes"), cve)
        record = (severity, package, version)
        if severity in EXPECTED_SEVERITIES:
            important[cve] = record
        else:
            lower.append({"cve": cve, "severity": severity, "package": package, "version": version})
    return important, lower


def validate_policy(
    allowlist_path: Path,
    scan_path: Path,
    *,
    platform: str,
    dockerfile_path: Path,
    today: date | None = None,
) -> list[dict[str, str]]:
    review_date = today or datetime.now(timezone.utc).date()
    allowed = _validate_allowlist(
        _load_json(allowlist_path),
        expected_platform=platform,
        dockerfile_path=dockerfile_path,
        today=review_date,
    )
    found, lower = _scan_findings(_load_json(scan_path))
    for cve, expected in allowed.items():
        if cve in found and found[cve] != expected:
            raise PolicyError(f"finding mismatch for {cve}: expected {expected}, found {found[cve]}")
    unexpected = sorted(set(found) - set(allowed))
    stale = sorted(set(allowed) - set(found))
    _require(not unexpected, f"unexpected CRITICAL/HIGH findings: {', '.join(unexpected)}")
    _require(not stale, f"stale allowlist entries absent from scan: {', '.join(stale)}")
    _require(len(found) == len(allowed) == 17, "completed scan and allowlist must contain exactly 17 important findings")
    return lower


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--dockerfile", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        lower = validate_policy(
            args.allowlist,
            args.scan,
            platform=args.platform,
            dockerfile_path=args.dockerfile,
            today=args.as_of,
        )
    except PolicyError as exc:
        print(f"ECR scan policy FAILED: {exc}", file=sys.stderr)
        return 1
    print("ECR scan policy PASSED: exactly 17 CRITICAL/HIGH findings are approved.")
    print(f"MEDIUM/LOW findings reported without failing policy: {len(lower)}")
    for finding in lower:
        print(
            f"{finding['severity']} {finding['cve']} "
            f"{finding['package']} {finding['version']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
