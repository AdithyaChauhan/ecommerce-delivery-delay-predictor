from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

from scripts.validate_ecr_scan import PolicyError, validate_policy


ROOT = Path(__file__).parents[1]
ALLOWLIST = ROOT / "security" / "ecr-scan-allowlist.json"
FIXTURE = ROOT / "tests" / "fixtures" / "ecr-scan-f33c05a-high-critical.json"
DOCKERFILE = ROOT / "Dockerfile"
PLATFORM = "linux/amd64"
AS_OF = date(2026, 9, 11)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def policy_data() -> dict:
    return load_json(ALLOWLIST)


def fixture_data() -> dict:
    return load_json(FIXTURE)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def run_validation(
    tmp_path: Path,
    policy: dict | None = None,
    scan: dict | None = None,
    *,
    platform: str = PLATFORM,
    dockerfile_path: Path = DOCKERFILE,
) -> list[dict[str, str]]:
    allowlist_path = tmp_path / "allowlist.json"
    scan_path = tmp_path / "scan.json"
    write_json(allowlist_path, policy if policy is not None else policy_data())
    write_json(scan_path, scan if scan is not None else fixture_data())
    return validate_policy(
        allowlist_path,
        scan_path,
        platform=platform,
        dockerfile_path=dockerfile_path,
        today=AS_OF,
    )


def test_allowlist_matches_independent_complete_fixture(tmp_path: Path):
    scan = fixture_data()
    findings = scan["imageScanFindings"]["findings"]
    assert scan["imageScanStatus"]["status"] == "COMPLETE"
    assert scan["imageScanFindings"]["findingSeverityCounts"] == {"CRITICAL": 6, "HIGH": 11}
    assert len(findings) == 17
    assert all(
        finding["name"].startswith("CVE-")
        and finding["severity"] in {"CRITICAL", "HIGH"}
        and finding["uri"].endswith(finding["name"])
        and {attribute["key"] for attribute in finding["attributes"]} >= {"package_name", "package_version"}
        for finding in findings
    )
    assert run_validation(tmp_path, scan=scan) == []


def test_unexpected_critical_or_high_finding_fails(tmp_path: Path):
    scan = fixture_data()
    scan["imageScanFindings"]["findings"].append(
        {
            "name": "CVE-2099-0001",
            "severity": "HIGH",
            "attributes": [
                {"key": "package_name", "value": "unknown"},
                {"key": "package_version", "value": "1.0"},
            ],
        }
    )
    with pytest.raises(PolicyError, match="unexpected CRITICAL/HIGH"):
        run_validation(tmp_path, scan=scan)


@pytest.mark.parametrize("field", ["severity", "package", "version"])
def test_finding_mismatch_fails(tmp_path: Path, field: str):
    scan = fixture_data()
    first = scan["imageScanFindings"]["findings"][0]
    if field == "severity":
        first[field] = "CRITICAL"
    else:
        first["attributes"][0 if field == "package" else 1]["value"] = "wrong"
    with pytest.raises(PolicyError, match="finding mismatch"):
        run_validation(tmp_path, scan=scan)


def test_duplicate_allowlist_entry_fails(tmp_path: Path):
    policy = policy_data()
    policy["exceptions"][1] = copy.deepcopy(policy["exceptions"][0])
    with pytest.raises(PolicyError, match="duplicate allowlist entry"):
        run_validation(tmp_path, policy=policy)


def test_expired_allowlist_entry_fails(tmp_path: Path):
    policy = policy_data()
    policy["exceptions"][0]["review_by"] = "2026-09-10"
    with pytest.raises(PolicyError, match="expired allowlist entry"):
        run_validation(tmp_path, policy=policy)


def test_stale_allowlist_entry_fails(tmp_path: Path):
    scan = fixture_data()
    scan["imageScanFindings"]["findings"].pop()
    with pytest.raises(PolicyError, match="stale allowlist entries"):
        run_validation(tmp_path, scan=scan)


def test_malformed_scan_fails(tmp_path: Path):
    scan = fixture_data()
    del scan["imageScanStatus"]
    with pytest.raises(PolicyError, match="scan status must be COMPLETE"):
        run_validation(tmp_path, scan=scan)


def test_medium_and_low_findings_are_reported_without_failure(tmp_path: Path):
    scan = fixture_data()
    lower = [
        {
            "name": "CVE-2099-0002",
            "severity": "MEDIUM",
            "attributes": [
                {"key": "package_name", "value": "demo-medium"},
                {"key": "package_version", "value": "1.0"},
            ],
        },
        {
            "name": "CVE-2099-0003",
            "severity": "LOW",
            "attributes": [
                {"key": "package_name", "value": "demo-low"},
                {"key": "package_version", "value": "1.0"},
            ],
        },
    ]
    scan["imageScanFindings"]["findings"].extend(lower)
    assert run_validation(tmp_path, scan=scan) == [
        {"cve": "CVE-2099-0002", "severity": "MEDIUM", "package": "demo-medium", "version": "1.0"},
        {"cve": "CVE-2099-0003", "severity": "LOW", "package": "demo-low", "version": "1.0"},
    ]


def test_mismatched_dockerfile_digest_fails(tmp_path: Path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "FROM python:3.13.15-slim-trixie@sha256:" + "0" * 64 + " AS runtime\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError, match="base digest does not match Dockerfile"):
        run_validation(tmp_path, dockerfile_path=dockerfile)


def test_unpinned_runtime_base_fails(tmp_path: Path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.13.15-slim-trixie AS runtime\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="sha256-pinned"):
        run_validation(tmp_path, dockerfile_path=dockerfile)


def test_platform_mismatch_fails(tmp_path: Path):
    with pytest.raises(PolicyError, match="platform does not match"):
        run_validation(tmp_path, platform="linux/arm64")


def test_workflow_push_filter_includes_policy_implementation_and_fixture_paths():
    workflow = (ROOT / ".github" / "workflows" / "ci-ecr.yml").read_text(encoding="utf-8")
    push_section = re.search(r"(?ms)^  push:.*?(?=^  workflow_dispatch:)", workflow)
    assert push_section is not None
    for path in (
        "security/ecr-scan-allowlist.json",
        "scripts/validate_ecr_scan.py",
        "tests/test_ecr_scan_policy.py",
        "tests/fixtures/ecr-scan-f33c05a-high-critical.json",
    ):
        assert f'- "{path}"' in push_section.group(0)
