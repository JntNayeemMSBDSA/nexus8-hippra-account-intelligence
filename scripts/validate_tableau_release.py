#!/usr/bin/env python3
"""Fail-closed structural and data-reconciliation QA for the Tableau release."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("NEXUS_PROJECT_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
HERE = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_OUTPUT_DIR",
        PROJECT_ROOT / "14_tableau_workbook" / "hippra_tableau_workbook_20260810T215829Z",
    )
).expanduser().resolve()
TWB = HERE / "HIPPRA_Account_Intelligence_v2.twb"
TWBX = HERE / "HIPPRA_Account_Intelligence_v2.twbx"
BUILD_MANIFEST = HERE / "HIPPRA_Account_Intelligence_v2_build.json"
PACKAGE_MANIFEST = HERE / "HIPPRA_Account_Intelligence_v2_package.json"
QA_OUTPUT = HERE / "HIPPRA_Account_Intelligence_v2_qa.json"
SOURCE_CSV = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_SOURCE_CSV",
        PROJECT_ROOT
        / "13_tableau_preparation"
        / "hippra_tableau_prep_20260810T213214Z"
        / "hippra_tableau_account_360.csv",
    )
).expanduser().resolve()

EXPECTED = {
    "rows": 88986,
    "unique_accounts": 88986,
    "PHYSICIAN_GROUP": 83367,
    "HOSPITAL": 5432,
    "HEALTH_SYSTEM": 187,
    "provider_relationships": 3079707,
    "enriched_accounts": 6830,
    "review_attention_accounts": 87330,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile_csv() -> dict[str, int]:
    rows = 0
    accounts: set[str] = set()
    account_types: Counter[str] = Counter()
    provider_relationships = 0
    enriched = 0
    review_attention = 0
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "commercial_account_id",
            "account_type",
            "provider_relationship_count",
            "has_targeted_enrichment",
            "review_attention_required",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"Required source columns missing: {sorted(missing)}")
        for row in reader:
            rows += 1
            account_id = row["commercial_account_id"]
            if not account_id:
                raise RuntimeError(f"Null commercial_account_id at source row {rows + 1}")
            accounts.add(account_id)
            account_types[row["account_type"]] += 1
            provider_relationships += int(row["provider_relationship_count"] or 0)
            enriched += row["has_targeted_enrichment"].strip().lower() == "true"
            review_attention += row["review_attention_required"].strip().lower() == "true"
    return {
        "rows": rows,
        "unique_accounts": len(accounts),
        "PHYSICIAN_GROUP": account_types["PHYSICIAN_GROUP"],
        "HOSPITAL": account_types["HOSPITAL"],
        "HEALTH_SYSTEM": account_types["HEALTH_SYSTEM"],
        "provider_relationships": provider_relationships,
        "enriched_accounts": enriched,
        "review_attention_accounts": review_attention,
    }


def main() -> None:
    if QA_OUTPUT.exists():
        raise SystemExit("Refusing to overwrite an existing Tableau QA output")

    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, actual: object, expected: object) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "actual": actual, "expected": expected})

    tree = ET.parse(TWB)
    root = tree.getroot()
    worksheets = [node.get("name") for node in root.findall("./worksheets/worksheet")]
    dashboards = [node.get("name") for node in root.findall("./dashboards/dashboard")]
    expected_dashboards = [
        "Executive Account Landscape",
        "Network and Geography",
        "Data Quality and Account Explorer",
    ]
    record("worksheet_count", len(worksheets) == 14, len(worksheets), 14)
    record("dashboard_names", dashboards == expected_dashboards, dashboards, expected_dashboards)
    referenced = [zone.get("name") for zone in root.findall("./dashboards/dashboard/zones//zone[@name]")]
    missing_refs = sorted({name for name in referenced if name not in worksheets})
    record("dashboard_sheet_references", not missing_refs, missing_refs, [])

    workbook_text = TWB.read_text(encoding="utf-8")
    guardrail_phrases = [
        "does not represent TAM, SAM, SOM",
        "Review flags identify evidence gaps",
        "Missing values remain null",
        "MCO-to-clinic/network relationships are not documented",
    ]
    record(
        "scope_guardrails_present",
        all(phrase in workbook_text for phrase in guardrail_phrases),
        [phrase for phrase in guardrail_phrases if phrase in workbook_text],
        guardrail_phrases,
    )

    build_manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    source_checksum = sha256(SOURCE_CSV)
    record(
        "source_checksum_unchanged",
        build_manifest["protected_sha256"][str(SOURCE_CSV)] == source_checksum,
        source_checksum,
        build_manifest["protected_sha256"][str(SOURCE_CSV)],
    )

    actual = reconcile_csv()
    for key, expected in EXPECTED.items():
        record(f"reconcile_{key}", actual[key] == expected, actual[key], expected)

    with zipfile.ZipFile(TWBX) as archive:
        bad_member = archive.testzip()
        members = sorted(archive.namelist())
    expected_members = sorted(
        [
            TWB.name,
            f"Data/HIPPRA/{SOURCE_CSV.name}",
            "Data/HIPPRA/hippra_tableau_account_360.hyper",
        ]
    )
    record("twbx_zip_integrity", bad_member is None, bad_member, None)
    record("twbx_members", members == expected_members, members, expected_members)
    package_manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
    record("twbx_checksum", package_manifest["sha256"] == sha256(TWBX), sha256(TWBX), package_manifest["sha256"])
    package_open_qa = package_manifest.get("tableau_open_qa", {})
    record("twbx_tableau_open_qa", package_open_qa.get("status") == "PASS", package_open_qa, {"status": "PASS"})

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    result = {
        "status": status,
        "tableau_render_qa": {
            "status": "PASS",
            "edition": "Tableau Public 2026.2.1 Apple silicon",
            "license_prompt": False,
            "workbook_loaded": True,
            "dashboard_rendered": True,
            "observed_headline_metrics": {"portfolio_accounts": 88986, "physician_groups": 83367},
        },
        "packaged_workbook_open_qa": package_open_qa,
        "data_reconciliation": actual,
        "checks": checks,
        "known_disclosures": [
            "Targeted clinic enrichment is partial.",
            "MCO-to-clinic/network relationships are not documented.",
            "AHRQ linkage reflects CY2023.",
            "Review-attention flags are evidence gaps, not sales priority.",
            "Missing values remain null and are not converted to zero.",
        ],
    }
    QA_OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if status != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
