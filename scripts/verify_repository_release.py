#!/usr/bin/env python3
"""Dependency-free verifier for the curated GitHub release."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TWB = ROOT / "dashboard" / "HIPPRA_Account_Intelligence_v2.twb"
TWBX = ROOT / "dashboard" / "HIPPRA_Account_Intelligence_v2.twbx"
QA = ROOT / "qa" / "HIPPRA_Account_Intelligence_v2_qa.json"
PACKAGE = ROOT / "qa" / "HIPPRA_Account_Intelligence_v2_package.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    failures: list[str] = []
    for path in (TWB, TWBX, QA, PACKAGE):
        if not path.is_file():
            failures.append(f"missing: {path.relative_to(ROOT)}")
    if failures:
        print("FAIL")
        print("\n".join(failures))
        sys.exit(1)

    qa = json.loads(QA.read_text(encoding="utf-8"))
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if qa.get("status") != "PASS":
        failures.append("release QA status is not PASS")
    if qa.get("packaged_workbook_open_qa", {}).get("status") != "PASS":
        failures.append("Tableau packaged-workbook open QA is not PASS")
    if package.get("sha256") != sha256(TWBX):
        failures.append("TWBX checksum does not match package manifest")

    root = ET.parse(TWB).getroot()
    worksheets = root.findall("./worksheets/worksheet")
    dashboards = root.findall("./dashboards/dashboard")
    if len(worksheets) != 14:
        failures.append(f"expected 14 worksheets; found {len(worksheets)}")
    if len(dashboards) != 3:
        failures.append(f"expected 3 dashboards; found {len(dashboards)}")

    expected_members = {
        "HIPPRA_Account_Intelligence_v2.twb",
        "Data/HIPPRA/hippra_tableau_account_360.csv",
        "Data/HIPPRA/hippra_tableau_account_360.hyper",
    }
    with zipfile.ZipFile(TWBX) as archive:
        if archive.testzip() is not None:
            failures.append("TWBX archive integrity failed")
        if set(archive.namelist()) != expected_members:
            failures.append("TWBX member list is unexpected")

    if failures:
        print("FAIL")
        print("\n".join(failures))
        sys.exit(1)
    print("PASS — curated Tableau release, package checksum, structure, and QA evidence verified")


if __name__ == "__main__":
    main()
