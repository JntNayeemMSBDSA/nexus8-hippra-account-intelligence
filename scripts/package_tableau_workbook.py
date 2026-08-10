#!/usr/bin/env python3
"""Create a portable local TWBX without publishing data to Tableau Public."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("NEXUS_PROJECT_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
HERE = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_OUTPUT_DIR",
        PROJECT_ROOT / "14_tableau_workbook" / "hippra_tableau_workbook_20260810T215829Z",
    )
).expanduser().resolve()
SOURCE_TWB = HERE / "HIPPRA_Account_Intelligence_v2.twb"
SOURCE_CSV = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_SOURCE_CSV",
        PROJECT_ROOT
        / "13_tableau_preparation"
        / "hippra_tableau_prep_20260810T213214Z"
        / "hippra_tableau_account_360.csv",
    )
).expanduser().resolve()
OUTPUT_TWBX = HERE / "HIPPRA_Account_Intelligence_v2.twbx"
PACKAGE_MANIFEST = HERE / "HIPPRA_Account_Intelligence_v2_package.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if OUTPUT_TWBX.exists() or PACKAGE_MANIFEST.exists():
        raise SystemExit("Refusing to overwrite an existing TWBX or package manifest")

    tree = ET.parse(SOURCE_TWB)
    root = tree.getroot()
    datasource = root.find("./datasources/datasource")
    if datasource is None:
        raise RuntimeError("Datasource missing from TWB")

    # Tableau Public requires packaged workbooks to use an extract. Embed the
    # certified Hyper that Tableau created from the certified account mart and
    # rewrite both source and extract connections to package-relative paths.
    extract_connection = datasource.find("./extract/connection[@class='hyper']")
    if extract_connection is None:
        raise RuntimeError("Certified Hyper extract connection missing from TWB")
    source_hyper = Path(extract_connection.get("dbname") or "")
    if not source_hyper.is_file():
        raise RuntimeError(f"Certified Hyper extract not found: {source_hyper}")
    protected_before = {str(p): sha256(p) for p in (SOURCE_TWB, SOURCE_CSV, source_hyper)}
    extract_connection.set("dbname", "Data/HIPPRA/hippra_tableau_account_360.hyper")
    connection = datasource.find(".//connection[@class='textscan']")
    if connection is None:
        raise RuntimeError("Certified text connection missing from TWB")
    connection.set("directory", "Data/HIPPRA")
    connection.set("filename", SOURCE_CSV.name)

    with tempfile.TemporaryDirectory(prefix="hippra-tableau-package-") as temporary:
        packaged_twb = Path(temporary) / SOURCE_TWB.name
        ET.indent(tree, space="  ")
        tree.write(packaged_twb, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(OUTPUT_TWBX, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(packaged_twb, arcname=SOURCE_TWB.name)
            archive.write(SOURCE_CSV, arcname=f"Data/HIPPRA/{SOURCE_CSV.name}")
            archive.write(source_hyper, arcname="Data/HIPPRA/hippra_tableau_account_360.hyper")

    protected_after = {str(p): sha256(p) for p in (SOURCE_TWB, SOURCE_CSV, source_hyper)}
    if protected_before != protected_after:
        OUTPUT_TWBX.unlink(missing_ok=True)
        raise RuntimeError("Protected input checksum changed during packaging")

    with zipfile.ZipFile(OUTPUT_TWBX) as archive:
        names = sorted(archive.namelist())
        bad_member = archive.testzip()
    manifest = {
        "status": "PACKAGED_WITH_CERTIFIED_EXTRACT_PENDING_TABLEAU_OPEN_QA",
        "output": str(OUTPUT_TWBX),
        "sha256": sha256(OUTPUT_TWBX),
        "bytes": OUTPUT_TWBX.stat().st_size,
        "members": names,
        "zip_integrity": "PASS" if bad_member is None else f"FAIL:{bad_member}",
        "protected_inputs_unchanged": True,
        "protected_sha256": protected_after,
        "publication_behavior": "LOCAL_ONLY_NOT_PUBLISHED_TO_TABLEAU_PUBLIC",
    }
    PACKAGE_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
