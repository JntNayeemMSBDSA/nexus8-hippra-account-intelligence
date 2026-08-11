# HIPPRA Account Intelligence

## From fragmented federal healthcare files to a tested account model

I started this project with a business question that sounded simple: which healthcare organizations can HIPPRA study, and how are providers, physician groups, hospitals, clinics, and health systems connected?

The source data did not contain a ready-made account table. It contained separate provider, hospital, affiliation, enrollment, ownership, clinic, and health-system files. Each source used a different identifier and a different level of detail. Some relationships were explicit. Others were only possible matches. Missing values often meant unavailable or inapplicable, not zero.

My work was to reconstruct the account layer without turning repeated enrollment records, name matches, or missing data into false business facts. I built and certified the data system first. I then created the account model, added controlled enrichment, and built Tableau only after the analytical output passed reconciliation and quality checks.

## Project at a glance

| Item | Detail |
|---|---|
| My role | Data scientist, analytics engineer, and Tableau developer |
| Domain | Healthcare provider and organizational account intelligence |
| Main tools | Python, SQL, DuckDB, Parquet, Hyper, Tableau |
| Final dashboard grain | One row per certified commercial account |
| Final account rows | 88,986 |
| Provider-account relationships | 3,079,707 |
| Tableau deliverable | 14 worksheets and 3 dashboards |
| Release result | 17 of 17 Tableau checks passed |

## The problem I had to solve

The business concept of an account did not map cleanly to one government file. Before I could analyze anything, I had to answer several data-modeling questions:

1. When should a provider organization become a physician-group account?
2. When do two affiliation rows represent duplicates, and when do they represent separate enrollment lineage?
3. How should a hospital owner differ from a health system?
4. When is a clinic match strong enough to accept, and when should it remain a candidate for review?
5. How can missing ratings, ownership percentages, and postal values stay visible without being converted into misleading zeroes?
6. Which commercial questions are supported by the data, and which ones require more evidence?

Those questions shaped the pipeline. The dashboard was the final layer, not the starting point.

## Data I worked with

The reconstruction combined fixed snapshots from CMS and other federal sources. The main inputs were:

| Source | Level of detail | How I used it |
|---|---|---|
| Medicare Physician and Other Practitioners, 1,296,739 rows | Provider | Provider identity and descriptive measures |
| CMS National Downloadable File | Provider, organization PAC ID, and practice location | Provider-to-group relationships and organization identity |
| CMS Facility Affiliation Data, 2,260,193 rows | NPI, PAC enrollment, and hospital CCN | Provider-to-hospital relationships |
| CMS Hospital General Information, 5,432 rows | Hospital CCN | Hospital identity, type, geography, and rating context |
| CMS Hospital Enrollments, 9,175 rows | Enrollment | Hospital enrollment lineage |
| CMS Hospital All Owners, 147,332 rows | Enrollment and owner | Ownership evidence and limited system-parent relationships |
| HRSA health-center sites, 19,039 rows | Clinic site and health-center number | Clinic and clinic-network enrichment |
| CMS FQHC and RHC enrollment files | Clinic enrollment | Authoritative clinic identity and candidate resolution |
| AHRQ 2023 system and hospital-linkage files | Health system and hospital CCN | Explicit hospital-to-system enrichment |
| Medicaid managed-care report | Program and plan | Plan identity only; it did not support clinic-level coverage links |

I stored source checksums, file sizes, row and column counts, schemas, encodings, release periods, and retrieval status. When a historical retrieval timestamp could not be proven, I recorded it as `NOT_RECORDED` instead of inventing one.

## What I did

### 1. Audited and certified the reconstructed data foundation

I treated the existing raw files, DuckDB database, Parquet outputs, and successful quality records as protected inputs. New work was written to versioned locations. Every stage used checksums and structured state files so a rerun could resume safely without overwriting a successful result.

During this audit I found a serious state-management problem. The analytical build had succeeded, but the project was later marked `FAILED`. The cause was not bad data. A success path supplied `status` twice when it updated pipeline state, after the valid outputs and readiness marker had already been written.

I preserved the contradictory historical record, repaired the future state-writing logic, and added regression tests for:

* successful completion;
* a real processing failure;
* stale PID files;
* interrupted cleanup;
* valid analysis-ready output;
* missing outputs;
* failed quality checks.

The repaired system distinguishes `RUNNING`, `BUILD_READY`, `RELEASE_CERTIFIED`, `FAILED`, and `HUMAN_INPUT_REQUIRED`.

### 2. Resolved the affiliation-grain problem without deleting evidence

The affiliation data contained 47 repeated NPI and CCN combinations. A quick cleanup would have dropped them as duplicates. I traced them to different PAC enrollment lineage and kept that distinction.

I created two valid analytical representations:

* NPI by hospital for provider-network counts;
* NPI by PAC enrollment by hospital when enrollment lineage matters.

This prevents inflated network counts while preserving the source history. The choice of grain is explicit rather than hidden inside a deduplication step.

### 3. Modeled missingness instead of replacing it with zero

Three quality problems needed separate handling:

* 2,250 hospitals had no overall rating. I kept the rating null and added availability, applicability, and missing-reason fields.
* 89,838 ownership rows had no ownership percentage. I kept those values null and added a missingness indicator. A missing percentage does not mean zero ownership.
* 27 provider postal values were not five-digit domestic ZIP codes. I classified domestic standard, domestic nonstandard, military, foreign, missing, and unresolved values without padding or truncating them.

CMS suppression markers also remained separate from numeric values. Blank and suppressed measures were never parsed as zero.

### 4. Turned the commercial definition into a data contract

I kept provider, clinic, physician group, hospital, health system, network, plan, account, and contract concepts separate. They are not interchangeable units.

The final identity rules were deliberately conservative:

* an organization PAC ID with an organization name can define a physician-group account;
* an organization NPI explicitly typed as `Clinic or Group Practice` can define a physician-group account;
* a CCN with a hospital name can define a hospital account;
* a PECOS owner associate ID with an explicit chain or home-office flag can define a limited health-system account.

Names and addresses alone never merge two authoritative identifiers. Exact name and location matches can create a review candidate, but not a final account. Fuzzy matching does not enter the certified account table.

### 5. Built the account marts and relationship bridges

I discovered source tables by their column signatures instead of hard-coding assumed table names. I then built separate structures for:

* commercial accounts;
* provider-to-account relationships;
* parent and child account relationships;
* unresolved relationship candidates;
* source gaps and evidence-review flags.

The account layer produced 83,367 physician groups, 5,432 hospitals, and 187 health systems. It also retained 306,718 physician-practice candidates and 4,041 health-system candidates outside the final account table because the available evidence was not strong enough to promote them.

### 6. Added targeted enrichment without changing certified identities

I added six versioned federal source snapshots for clinics, clinic networks, managed-care plans, and AHRQ health systems. This was a separate, joinable layer rather than a rewrite of the account mart.

The enrichment work identified:

* 35,789 authoritative clinic records;
* 1,526 clinic networks;
* 19,039 explicit clinic-to-network relationships;
* 639 AHRQ health systems;
* 4,193 explicit hospital-to-system relationships;
* 818 managed-care plan identities.

The managed-care source did not document plan-to-clinic coverage. I therefore left that bridge empty. Creating a plausible-looking relationship would have produced a more complete dashboard, but it would not have been supported by the source.

### 7. Prepared the Tableau layer at a stable grain

The Tableau source contains 57 fields and one row per `commercial_account_id`. I kept identifiers as dimensions, used additive relationship measures only where valid, and carried review flags and scope notes into the presentation layer.

I built three dashboards:

1. **Executive Account Landscape** shows account counts, account mix, provider relationships, leading accounts, and enrichment coverage.
2. **Network and Geography** explores approved state geography and provider-to-account network structure.
3. **Data Quality and Account Explorer** exposes enrichment coverage, the evidence-review queue, and account-level details.

The workbook contains 14 worksheets and is packaged with its certified Hyper extract so it opens without a database connection.

## How the pieces fit together

```mermaid
flowchart LR
    A["Fixed federal source snapshots"] --> B["Certified DuckDB and Parquet foundation"]
    B --> C["Commercial definition contract"]
    C --> D["Account marts and relationship bridges"]
    D --> E["Targeted enrichment and review candidates"]
    E --> F["One-row-per-account Tableau source"]
    F --> G["TWB and portable TWBX"]
    G --> H["Reconciliation, package, and open tests"]
```

## Final result

| Measure | Certified value |
|---|---:|
| Commercial accounts | 88,986 |
| Physician groups | 83,367 |
| Hospitals | 5,432 |
| Health systems | 187 |
| Provider-account relationships | 3,079,707 |
| Providers linked to at least one final account | 1,072,710 of 1,296,739 |
| Accounts with targeted enrichment | 6,830 |
| Accounts carrying an evidence-review flag | 87,330 |

![Certified account and quality summary](assets/release-summary.svg)

The review count is intentionally high. It indicates incomplete or unresolved evidence, not low commercial value. It is not a sales-priority score.

## How I tested the release

The final validation checked both the data and the Tableau package:

* account rows reconciled to unique account IDs;
* account-type counts and provider relationships matched the certified source;
* protected source checksums remained unchanged;
* the TWBX archive passed integrity checks;
* the expected TWB, CSV, and Hyper members were present;
* all 14 worksheets and all 3 dashboards were found;
* required scope warnings were present;
* Tableau Public 2026.2.1 loaded and opened the packaged workbook with zero detailed errors.

The result was 17 passed checks out of 17.

Run the repository-level verification with:

```bash
python3 scripts/verify_repository_release.py
```

## Open the workbook

1. Install Tableau Public Desktop Edition 2026.2.1 or later.
2. Download [`HIPPRA_Account_Intelligence_v2.twbx`](dashboard/HIPPRA_Account_Intelligence_v2.twbx).
3. Open the file locally in Tableau Public.

The packaged workbook includes its certified extract. No database connection is required.

## What this repository contains

This is a curated portfolio release. It includes the final workbook, the dashboard-facing semantic documentation, deterministic workbook and packaging code, and machine-readable quality evidence.

The large raw snapshots, the local DuckDB database, and confidential commercial source notes are not copied into this public repository. Because of that boundary, this repository verifies and rebuilds the Tableau release from the certified presentation input; it is not a raw-data download bundle for recreating every upstream stage from zero.

```text
dashboard/  Tableau TWB and portable TWBX
scripts/    workbook generation, packaging, validation, and release verification
qa/         versioned build, package, reconciliation, and enrichment evidence
docs/       architecture, field definitions, methodology, and build guidance
assets/     project visuals
```

## Claims I did not make

This project describes the account landscape and its evidence quality. It does not claim that the account count represents TAM, SAM, or SOM. It does not label an organization as a customer, prospect, eligible buyer, or sales priority. It does not calculate pricing, contract value, revenue, churn, or forecasts.

The current certified analytical system is DuckDB and Parquet. I did not execute this reconstructed pipeline in SQL Server. SQL Server DDL, transformations, and reconciliation would be a separate future stage.

## What I learned

The hardest part was not writing a join or drawing a chart. It was deciding what the rows were allowed to mean.

An exact name match is not automatically the same organization. A repeated provider-to-hospital key is not automatically a duplicate. A missing ownership percentage is not zero. A useful commercial hypothesis is not the same thing as source evidence.

Making those distinctions explicit produced a smaller set of final claims, but a much more defensible project.
